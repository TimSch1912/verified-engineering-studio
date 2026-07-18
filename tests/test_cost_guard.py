import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from ves.core.cost_guard import CostGuard
from ves.core.models import EngineeringVerdict, Finding
from ves.core.review import ReviewService
from ves.modules.cfd import CFDModule


class MutableClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def __call__(self) -> datetime:
        return self.current

    def advance(self, **kwargs: int) -> None:
        self.current += timedelta(**kwargs)


def cfd_evidence_and_checks():
    module = CFDModule()
    evidence = module.build_evidence("laurons-v9")
    return evidence, module.validate(evidence)


def sample_verdict() -> EngineeringVerdict:
    return EngineeringVerdict(
        status="verified",
        summary="Structured evidence review completed.",
        findings=[
            Finding(
                severity="positive",
                title="Evidence is traceable",
                detail="The finding cites a supplied metric.",
                evidence_refs=["metric.total_resistance"],
            )
        ],
        caveats=[],
        next_actions=["Complete the remaining verification step."],
        evidence_refs=["metric.total_resistance"],
    )


def make_guard(tmp_path, **overrides) -> CostGuard:
    options = {
        "db_path": tmp_path / "guard.sqlite3",
        "client_limit": 3,
        "client_window_seconds": 3600,
        "daily_limit": 20,
        "cache_ttl_seconds": 604800,
        "max_concurrent": 1,
        "identity_secret": b"test-identity-secret-that-is-long-enough",
    }
    options.update(overrides)
    return CostGuard(**options)


def test_no_key_uses_fallback_without_reserving_quota(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    guard = make_guard(tmp_path)
    service = ReviewService(cost_guard=guard)
    evidence, checks = cfd_evidence_and_checks()
    client_id = guard.client_identity("203.0.113.10")

    result = asyncio.run(service.review(evidence, checks, "Assess the result", client_id=client_id))

    assert result.provenance.mode == "deterministic-fallback"
    assert result.provenance.fallback_reason == "not_configured"
    assert result.provenance.live_api_call is False
    assert guard.snapshot(client_id).client.remaining == 3
    assert guard.snapshot(client_id).daily.remaining == 20


def test_success_is_cached_persistently_and_timestamp_is_semantic_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    guard = make_guard(tmp_path)
    service = ReviewService(cost_guard=guard)
    evidence, checks = cfd_evidence_and_checks()
    client_id = guard.client_identity("203.0.113.11")
    calls = []

    async def fake_review(_evidence, _checks, question):
        calls.append(question)
        return sample_verdict()

    monkeypatch.setattr(service, "_gpt_review", fake_review)
    first = asyncio.run(
        service.review(evidence, checks, " Assess   the result ", client_id=client_id)
    )
    second = asyncio.run(service.review(evidence, checks, "Assess the result", client_id=client_id))

    assert first.provenance.mode == "gpt-5.6"
    assert first.provenance.live_api_call is True
    assert first.provenance.cache_hit is False
    assert first.verdict.status == "review"
    assert second.provenance.cache_hit is True
    assert second.provenance.live_api_call is False
    assert calls == ["Assess the result"]

    second_guard = make_guard(tmp_path)
    second_service = ReviewService(cost_guard=second_guard)

    async def unexpected_call(*_args):
        raise AssertionError("persistent cache should prevent another API call")

    monkeypatch.setattr(second_service, "_gpt_review", unexpected_call)
    changed_timestamp = evidence.model_copy(
        update={"generated_at": evidence.generated_at + timedelta(minutes=5)}
    )
    third = asyncio.run(
        second_service.review(
            changed_timestamp,
            checks,
            "Assess the result",
            client_id=second_guard.client_identity("203.0.113.11"),
        )
    )
    assert third.provenance.cache_hit is True
    assert third.provenance.evidence_sha256 != first.provenance.evidence_sha256


def test_client_and_daily_limits_fail_to_free_deterministic_review(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    guard = make_guard(tmp_path, client_limit=2, daily_limit=3)
    service = ReviewService(cost_guard=guard)
    evidence, checks = cfd_evidence_and_checks()
    first_client = guard.client_identity("203.0.113.12")
    second_client = guard.client_identity("203.0.113.13")
    calls = []

    async def fake_review(_evidence, _checks, question):
        calls.append(question)
        return sample_verdict()

    monkeypatch.setattr(service, "_gpt_review", fake_review)
    for question in ("Question one", "Question two"):
        result = asyncio.run(service.review(evidence, checks, question, client_id=first_client))
        assert result.provenance.mode == "gpt-5.6"

    client_limited = asyncio.run(
        service.review(evidence, checks, "Question three", client_id=first_client)
    )
    assert client_limited.provenance.fallback_reason == "client_limit"
    assert client_limited.verdict.status == "review"

    third_live = asyncio.run(
        service.review(evidence, checks, "Question three", client_id=second_client)
    )
    assert third_live.provenance.mode == "gpt-5.6"
    daily_limited = asyncio.run(
        service.review(evidence, checks, "Question four", client_id=second_client)
    )
    assert daily_limited.provenance.fallback_reason == "daily_limit"

    cached_after_limits = asyncio.run(
        service.review(evidence, checks, "Question one", client_id=first_client)
    )
    assert cached_after_limits.provenance.cache_hit is True
    assert calls == ["Question one", "Question two", "Question three"]


def test_api_error_counts_attempt_and_is_not_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    guard = make_guard(tmp_path, client_limit=1)
    service = ReviewService(cost_guard=guard)
    evidence, checks = cfd_evidence_and_checks()
    client_id = guard.client_identity("203.0.113.14")
    calls = 0

    async def failing_review(*_args):
        nonlocal calls
        calls += 1
        raise TimeoutError("upstream timeout")

    monkeypatch.setattr(service, "_gpt_review", failing_review)
    first = asyncio.run(service.review(evidence, checks, "First try", client_id=client_id))
    second = asyncio.run(service.review(evidence, checks, "Second try", client_id=client_id))

    assert first.provenance.fallback_reason == "api_error"
    assert first.provenance.api_error is True
    assert first.provenance.live_api_call is True
    assert second.provenance.fallback_reason == "client_limit"
    assert calls == 1


def test_invalid_cached_verdict_fails_closed_without_api_call(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    guard = make_guard(tmp_path)
    service = ReviewService(cost_guard=guard)
    evidence, checks = cfd_evidence_and_checks()
    question = "Assess this cached result"
    guard.put_cached(service._cache_key(evidence, checks, question), "not valid JSON")

    async def unexpected_call(*_args):
        raise AssertionError("an invalid cache entry must fail closed")

    monkeypatch.setattr(service, "_gpt_review", unexpected_call)
    result = asyncio.run(service.review(evidence, checks, question, client_id="client"))

    assert result.provenance.fallback_reason == "guard_error"
    assert result.provenance.live_api_call is False
    assert guard.snapshot("client").daily.remaining == 20


def test_busy_and_storage_failure_never_call_openai(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    evidence, checks = cfd_evidence_and_checks()

    guard = make_guard(tmp_path)
    service = ReviewService(cost_guard=guard)

    async def unexpected_call(*_args):
        raise AssertionError("guarded requests must not call OpenAI")

    monkeypatch.setattr(service, "_gpt_review", unexpected_call)
    assert guard.try_acquire_live_slot() is True
    try:
        busy = asyncio.run(service.review(evidence, checks, "Busy request", client_id="client"))
    finally:
        guard.release_live_slot()
    assert busy.provenance.fallback_reason == "busy"

    invalid_db_path = tmp_path / "database-is-a-directory"
    invalid_db_path.mkdir()
    broken_guard = make_guard(tmp_path, db_path=invalid_db_path)
    broken_service = ReviewService(cost_guard=broken_guard)
    monkeypatch.setattr(broken_service, "_gpt_review", unexpected_call)
    guarded = asyncio.run(
        broken_service.review(evidence, checks, "Guard failure", client_id="client")
    )
    assert guarded.provenance.fallback_reason == "guard_error"


def test_atomic_daily_reservation_and_utc_reset(tmp_path):
    clock = MutableClock(datetime(2026, 7, 18, 10, 0, tzinfo=UTC))
    guard = make_guard(tmp_path, daily_limit=1, client_limit=10, clock=clock)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda index: guard.reserve_live_call(f"client-{index}"), range(8)))
    assert sum(result.allowed for result in results) == 1
    assert sum(result.reason == "daily_limit" for result in results) == 7

    clock.advance(days=1)
    reset = guard.reserve_live_call("client-next-day")
    assert reset.allowed is True


def test_database_stores_neither_raw_client_address_nor_question(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    guard = make_guard(tmp_path)
    service = ReviewService(cost_guard=guard)
    evidence, checks = cfd_evidence_and_checks()
    address = "198.51.100.77"
    question = "Is this private-looking raw question stored anywhere?"

    async def fake_review(*_args):
        return sample_verdict()

    monkeypatch.setattr(service, "_gpt_review", fake_review)
    asyncio.run(
        service.review(
            evidence,
            checks,
            question,
            client_id=guard.client_identity(address),
        )
    )

    with sqlite3.connect(guard.db_path) as connection:
        client_values = [
            row[0] for row in connection.execute("SELECT client_id FROM client_attempts")
        ]
        cache_payloads = [row[0] for row in connection.execute("SELECT payload FROM review_cache")]
    assert address not in client_values
    assert all(question not in payload for payload in cache_payloads)


def test_openai_client_disables_retries_and_bounds_output(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    guard = make_guard(tmp_path)
    service = ReviewService(
        cost_guard=guard,
        max_output_tokens=1800,
        timeout_seconds=45,
    )
    evidence, checks = cfd_evidence_and_checks()
    captured = {}

    class FakeResponses:
        async def parse(self, **kwargs):
            captured["parse"] = kwargs
            return SimpleNamespace(
                output_parsed=sample_verdict(),
                output=[],
                usage=SimpleNamespace(input_tokens=10, output_tokens=20, total_tokens=30),
            )

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.responses = FakeResponses()

    monkeypatch.setattr("ves.core.review.AsyncOpenAI", FakeClient)
    asyncio.run(service._gpt_review(evidence, checks, "Assess the evidence"))

    assert captured["client"] == {"timeout": 45, "max_retries": 0}
    assert captured["parse"]["store"] is False
    assert captured["parse"]["max_output_tokens"] == 1800
