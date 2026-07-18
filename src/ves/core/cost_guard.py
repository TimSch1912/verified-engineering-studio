from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

GuardReason = Literal["client_limit", "daily_limit", "busy", "guard_error"]


class CostGuardError(RuntimeError):
    """Raised when the persistent cost guard cannot fail closed safely."""


@dataclass(frozen=True)
class QuotaSnapshot:
    limit: int
    remaining: int
    reset_at: datetime


@dataclass(frozen=True)
class GuardSnapshot:
    client: QuotaSnapshot
    daily: QuotaSnapshot
    busy: bool


@dataclass(frozen=True)
class Reservation:
    allowed: bool
    reason: GuardReason | None
    snapshot: GuardSnapshot


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


class CostGuard:
    """Persistent quotas and cache for the public, unauthenticated review endpoint.

    Only HMAC identities are persisted. Raw client addresses and review questions are never
    written as quota or cache-key fields.
    """

    def __init__(
        self,
        *,
        db_path: str | Path,
        client_limit: int = 3,
        client_window_seconds: int = 3600,
        daily_limit: int = 20,
        cache_ttl_seconds: int = 604800,
        max_concurrent: int = 1,
        clock: Callable[[], datetime] | None = None,
        identity_secret: str | bytes | None = None,
    ) -> None:
        if client_limit < 1:
            raise ValueError("client_limit must be at least 1")
        if client_window_seconds < 60:
            raise ValueError("client_window_seconds must be at least 60")
        if daily_limit < 0:
            raise ValueError("daily_limit cannot be negative")
        if cache_ttl_seconds < 60:
            raise ValueError("cache_ttl_seconds must be at least 60")
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be at least 1")

        self.db_path = Path(db_path)
        self.client_limit = client_limit
        self.client_window_seconds = client_window_seconds
        self.daily_limit = daily_limit
        self.cache_ttl_seconds = cache_ttl_seconds
        self.max_concurrent = max_concurrent
        self._clock = clock or (lambda: datetime.now(UTC))
        self._configured_secret = (
            identity_secret.encode("utf-8") if isinstance(identity_secret, str) else identity_secret
        )
        self._identity_secret: bytes | None = None
        self._secret_lock = threading.Lock()
        self._database_lock = threading.Lock()
        self._database_ready = False
        self._active_lock = threading.Lock()
        self._active_live_calls = 0

    @classmethod
    def from_env(cls) -> CostGuard:
        return cls(
            db_path=os.getenv("VES_STATE_DB", ".state/review-guard.sqlite3"),
            client_limit=_env_int("VES_CLIENT_LIVE_REVIEW_LIMIT", 3, 1, 1000),
            client_window_seconds=_env_int("VES_CLIENT_WINDOW_SECONDS", 3600, 60, 86400),
            daily_limit=_env_int("VES_DAILY_LIVE_REVIEW_LIMIT", 20, 0, 10000),
            cache_ttl_seconds=_env_int("VES_REVIEW_CACHE_TTL_SECONDS", 604800, 60, 2592000),
            max_concurrent=_env_int("VES_MAX_CONCURRENT_LIVE_REVIEWS", 1, 1, 20),
            identity_secret=os.getenv("VES_RATE_LIMIT_SECRET"),
        )

    def client_identity(self, address: str) -> str:
        normalized = address.strip().lower() or "unknown"
        return hmac.new(
            self._get_identity_secret(), normalized.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def get_cached(self, cache_key: str) -> str | None:
        now = self._now()
        cutoff = now.timestamp() - self.cache_ttl_seconds
        try:
            connection = self._connect()
            try:
                row = connection.execute(
                    "SELECT payload, created_at FROM review_cache WHERE cache_key = ?",
                    (cache_key,),
                ).fetchone()
                if row is None:
                    return None
                payload, created_at = row
                if float(created_at) < cutoff:
                    connection.execute("DELETE FROM review_cache WHERE cache_key = ?", (cache_key,))
                    connection.commit()
                    return None
                return str(payload)
            finally:
                connection.close()
        except (OSError, sqlite3.Error) as exc:
            raise CostGuardError("review cache is unavailable") from exc

    def put_cached(self, cache_key: str, payload: str) -> None:
        now = self._now().timestamp()
        cutoff = now - self.cache_ttl_seconds
        try:
            connection = self._connect()
            try:
                connection.execute(
                    """
                    INSERT INTO review_cache(cache_key, created_at, payload)
                    VALUES (?, ?, ?)
                    ON CONFLICT(cache_key) DO UPDATE SET
                        created_at = excluded.created_at,
                        payload = excluded.payload
                    """,
                    (cache_key, now, payload),
                )
                connection.execute("DELETE FROM review_cache WHERE created_at < ?", (cutoff,))
                connection.commit()
            finally:
                connection.close()
        except (OSError, sqlite3.Error) as exc:
            raise CostGuardError("review cache could not be updated") from exc

    def reserve_live_call(self, client_id: str) -> Reservation:
        now = self._now()
        cutoff = now.timestamp() - self.client_window_seconds
        day = now.date().isoformat()
        try:
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "DELETE FROM client_attempts WHERE occurred_at < ?",
                    (cutoff,),
                )
                client_rows = connection.execute(
                    """
                    SELECT occurred_at FROM client_attempts
                    WHERE client_id = ? ORDER BY occurred_at ASC
                    """,
                    (client_id,),
                ).fetchall()
                daily_row = connection.execute(
                    "SELECT attempts FROM daily_attempts WHERE day = ?", (day,)
                ).fetchone()
                daily_used = int(daily_row[0]) if daily_row else 0

                snapshot = self._snapshot(now, client_rows, daily_used)
                if len(client_rows) >= self.client_limit:
                    connection.rollback()
                    return Reservation(False, "client_limit", snapshot)
                if daily_used >= self.daily_limit:
                    connection.rollback()
                    return Reservation(False, "daily_limit", snapshot)

                connection.execute(
                    "INSERT INTO client_attempts(client_id, occurred_at) VALUES (?, ?)",
                    (client_id, now.timestamp()),
                )
                connection.execute(
                    """
                    INSERT INTO daily_attempts(day, attempts) VALUES (?, 1)
                    ON CONFLICT(day) DO UPDATE SET attempts = attempts + 1
                    """,
                    (day,),
                )
                oldest_day = (now - timedelta(days=14)).date().isoformat()
                connection.execute("DELETE FROM daily_attempts WHERE day < ?", (oldest_day,))
                connection.commit()
                updated_rows = [*client_rows, (now.timestamp(),)]
                return Reservation(
                    True,
                    None,
                    self._snapshot(now, updated_rows, daily_used + 1),
                )
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()
        except (OSError, sqlite3.Error) as exc:
            raise CostGuardError("live-review quotas are unavailable") from exc

    def snapshot(self, client_id: str) -> GuardSnapshot:
        now = self._now()
        cutoff = now.timestamp() - self.client_window_seconds
        day = now.date().isoformat()
        try:
            connection = self._connect()
            try:
                connection.execute(
                    "DELETE FROM client_attempts WHERE occurred_at < ?",
                    (cutoff,),
                )
                client_rows = connection.execute(
                    """
                    SELECT occurred_at FROM client_attempts
                    WHERE client_id = ? ORDER BY occurred_at ASC
                    """,
                    (client_id,),
                ).fetchall()
                daily_row = connection.execute(
                    "SELECT attempts FROM daily_attempts WHERE day = ?", (day,)
                ).fetchone()
                daily_used = int(daily_row[0]) if daily_row else 0
                connection.commit()
                return self._snapshot(now, client_rows, daily_used)
            finally:
                connection.close()
        except (OSError, sqlite3.Error) as exc:
            raise CostGuardError("live-review quota status is unavailable") from exc

    def try_acquire_live_slot(self) -> bool:
        with self._active_lock:
            if self._active_live_calls >= self.max_concurrent:
                return False
            self._active_live_calls += 1
            return True

    def release_live_slot(self) -> None:
        with self._active_lock:
            self._active_live_calls = max(0, self._active_live_calls - 1)

    def _snapshot(
        self, now: datetime, client_rows: list[tuple[float]], daily_used: int
    ) -> GuardSnapshot:
        client_used = len(client_rows)
        if client_rows:
            client_reset = datetime.fromtimestamp(
                float(client_rows[0][0]) + self.client_window_seconds, UTC
            )
        else:
            client_reset = now + timedelta(seconds=self.client_window_seconds)
        next_day = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), UTC)
        with self._active_lock:
            busy = self._active_live_calls >= self.max_concurrent
        return GuardSnapshot(
            client=QuotaSnapshot(
                limit=self.client_limit,
                remaining=max(0, self.client_limit - client_used),
                reset_at=client_reset,
            ),
            daily=QuotaSnapshot(
                limit=self.daily_limit,
                remaining=max(0, self.daily_limit - daily_used),
                reset_at=next_day,
            ),
            busy=busy,
        )

    def _connect(self) -> sqlite3.Connection:
        self._ensure_database()
        connection = sqlite3.connect(self.db_path, timeout=5)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _ensure_database(self) -> None:
        if self._database_ready:
            return
        with self._database_lock:
            if self._database_ready:
                return
            try:
                self.db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                connection = sqlite3.connect(self.db_path, timeout=5)
                try:
                    connection.execute("PRAGMA journal_mode = WAL")
                    connection.execute(
                        """
                        CREATE TABLE IF NOT EXISTS review_cache(
                            cache_key TEXT PRIMARY KEY,
                            created_at REAL NOT NULL,
                            payload TEXT NOT NULL
                        )
                        """
                    )
                    connection.execute(
                        """
                        CREATE TABLE IF NOT EXISTS client_attempts(
                            client_id TEXT NOT NULL,
                            occurred_at REAL NOT NULL
                        )
                        """
                    )
                    connection.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_client_attempts
                        ON client_attempts(client_id, occurred_at)
                        """
                    )
                    connection.execute(
                        """
                        CREATE TABLE IF NOT EXISTS daily_attempts(
                            day TEXT PRIMARY KEY,
                            attempts INTEGER NOT NULL
                        )
                        """
                    )
                    connection.commit()
                finally:
                    connection.close()
                self._database_ready = True
            except (OSError, sqlite3.Error) as exc:
                raise CostGuardError("cost-guard database could not be initialized") from exc

    def _get_identity_secret(self) -> bytes:
        if self._configured_secret:
            return self._configured_secret
        if self._identity_secret:
            return self._identity_secret
        with self._secret_lock:
            if self._identity_secret:
                return self._identity_secret
            secret_path = self.db_path.with_suffix(self.db_path.suffix + ".identity")
            try:
                secret_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                if secret_path.exists():
                    value = secret_path.read_bytes()
                else:
                    value = secrets.token_bytes(32)
                    descriptor = os.open(
                        secret_path,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                        0o600,
                    )
                    with os.fdopen(descriptor, "wb") as handle:
                        handle.write(value)
                if len(value) < 32:
                    raise CostGuardError("rate-limit identity secret is invalid")
                self._identity_secret = value
                return value
            except FileExistsError:
                value = secret_path.read_bytes()
                if len(value) < 32:
                    raise CostGuardError("rate-limit identity secret is invalid")
                self._identity_secret = value
                return value
            except OSError as exc:
                raise CostGuardError("rate-limit identity secret is unavailable") from exc

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ValueError("cost-guard clock must return a timezone-aware datetime")
        return value.astimezone(UTC)
