from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ves.core.models import EvidenceBundle

MAX_MANIFEST_BYTES = 256 * 1024
MAX_HASH_FILE_BYTES = 256 * 1024
DEFAULT_MAX_FILE_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_TOTAL_BYTES = 250 * 1024 * 1024
DEFAULT_MAX_FILES = 128

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SECRET_PATTERNS = (
    re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bOPENAI_API_KEY\b\s*[:=]", re.IGNORECASE),
)
_PRIVATE_PATH_RE = re.compile(r"(?:^|[\s\"'])(?:/(?:home|Users)/|[A-Za-z]:\\+Users\\+)")
_TEXT_SUFFIXES = {".json", ".csv", ".md", ".txt", ".yaml", ".yml"}

PackageFileRole = Literal["evidence", "provenance", "timeseries", "artifact", "report"]
PublicationScope = Literal["public", "internal", "private"]


class PackageValidationError(ValueError):
    """Raised when a package cannot cross the read-only evidence boundary."""


class AdapterDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9._-]+$")
    version: str


class PackageFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    role: PackageFileRole
    sha256: str
    size_bytes: int = Field(ge=0)
    media_type: str

    @field_validator("path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        if not value or "\\" in value or any(ord(char) < 32 for char in value):
            raise ValueError("package file path must be a clean POSIX path")
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or value != path.as_posix():
            raise ValueError("package file path must be canonical and relative")
        if value in {"manifest.json", "source-hashes.sha256"}:
            raise ValueError("manifest and hash index cannot hash themselves")
        return value

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        normalized = value.lower()
        if not _SHA256_RE.fullmatch(normalized):
            raise ValueError("sha256 must contain 64 hexadecimal characters")
        return normalized


class EvidencePackageManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ves.package.v1"] = "ves.package.v1"
    package_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]+$")
    project_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]+$")
    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]+$")
    run_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]+$")
    module_id: str = Field(pattern=r"^[a-z][a-z0-9_-]+$")
    created_at: datetime
    publication_scope: PublicationScope
    adapter: AdapterDescriptor
    files: list[PackageFile] = Field(min_length=2)

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must include a timezone")
        return value


class ProvenanceProducer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    version: str


class PackageProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ves.provenance.v1"] = "ves.provenance.v1"
    producer: ProvenanceProducer
    source_system: str
    source_run_id: str
    source_created_at: datetime
    display: dict[str, str]
    publication_note: str

    @field_validator("source_created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("source_created_at must include a timezone")
        return value


@dataclass(frozen=True)
class ValidatedEvidencePackage:
    root: Path
    manifest: EvidencePackageManifest
    provenance: PackageProvenance
    evidence: EvidenceBundle
    package_sha256: str
    total_bytes: int


def validate_evidence_package(
    package_path: str | Path,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
) -> ValidatedEvidencePackage:
    """Validate and load a directory-form `.vespack` without executing package content."""

    root_input = Path(package_path)
    if root_input.is_symlink():
        raise PackageValidationError("package root must not be a symbolic link")
    if not root_input.is_dir():
        raise PackageValidationError("package path must be an existing directory")
    root = root_input.resolve()

    manifest_path = _required_regular_file(root, "manifest.json", MAX_MANIFEST_BYTES)
    hash_index_path = _required_regular_file(root, "source-hashes.sha256", MAX_HASH_FILE_BYTES)
    manifest_raw = _load_json(manifest_path)
    try:
        manifest = EvidencePackageManifest.model_validate(manifest_raw)
    except ValidationError as exc:
        raise PackageValidationError(f"manifest schema validation failed: {exc}") from exc

    if len(manifest.files) > max_files:
        raise PackageValidationError(f"package declares more than {max_files} files")
    declared_paths = [item.path for item in manifest.files]
    if len(declared_paths) != len(set(declared_paths)):
        raise PackageValidationError("manifest contains duplicate file paths")
    roles = [item.role for item in manifest.files]
    if roles.count("evidence") != 1 or roles.count("provenance") != 1:
        raise PackageValidationError(
            "package requires exactly one evidence and one provenance file"
        )

    actual_paths: set[str] = set()
    for entry in root.rglob("*"):
        if entry.is_symlink():
            raise PackageValidationError(
                f"symbolic links are not allowed: {entry.relative_to(root).as_posix()}"
            )
        if entry.is_dir():
            continue
        if not entry.is_file():
            raise PackageValidationError(
                f"special filesystem entries are not allowed: {entry.relative_to(root).as_posix()}"
            )
        actual_paths.add(entry.relative_to(root).as_posix())

    allowed_paths = {"manifest.json", "source-hashes.sha256", *declared_paths}
    undeclared = sorted(actual_paths - allowed_paths)
    missing = sorted(allowed_paths - actual_paths)
    if undeclared:
        raise PackageValidationError(f"package contains undeclared files: {', '.join(undeclared)}")
    if missing:
        raise PackageValidationError(f"package is missing declared files: {', '.join(missing)}")

    hash_index = _load_hash_index(hash_index_path)
    if set(hash_index) != set(declared_paths):
        raise PackageValidationError(
            "source-hashes.sha256 must list every declared file exactly once"
        )

    total_bytes = 0
    file_bytes: dict[str, bytes] = {}
    for item in manifest.files:
        candidate = (root / item.path).resolve()
        if not candidate.is_relative_to(root):
            raise PackageValidationError(f"package path escapes its root: {item.path}")
        if candidate.stat().st_mode & 0o111:
            raise PackageValidationError(f"executable package files are not allowed: {item.path}")
        size = candidate.stat().st_size
        if size > max_file_bytes:
            raise PackageValidationError(f"package file exceeds size limit: {item.path}")
        if size != item.size_bytes:
            raise PackageValidationError(f"declared size does not match file: {item.path}")
        total_bytes += size
        if total_bytes > max_total_bytes:
            raise PackageValidationError("package exceeds total size limit")
        payload = candidate.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if digest != item.sha256 or digest != hash_index[item.path]:
            raise PackageValidationError(f"sha256 mismatch: {item.path}")
        if candidate.suffix.lower() in _TEXT_SUFFIXES:
            _reject_private_material(item.path, payload)
        if item.role in {"evidence", "provenance"}:
            file_bytes[item.path] = payload

    evidence_file = next(item for item in manifest.files if item.role == "evidence")
    provenance_file = next(item for item in manifest.files if item.role == "provenance")
    evidence_raw = _decode_json(evidence_file.path, file_bytes[evidence_file.path])
    provenance_raw = _decode_json(provenance_file.path, file_bytes[provenance_file.path])
    try:
        evidence = EvidenceBundle.model_validate(evidence_raw)
        provenance = PackageProvenance.model_validate(provenance_raw)
    except ValidationError as exc:
        raise PackageValidationError(f"package payload schema validation failed: {exc}") from exc

    _validate_cross_references(manifest, evidence, provenance)
    canonical_manifest = json.dumps(
        manifest.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return ValidatedEvidencePackage(
        root=root,
        manifest=manifest,
        provenance=provenance,
        evidence=evidence,
        package_sha256=hashlib.sha256(canonical_manifest).hexdigest(),
        total_bytes=total_bytes,
    )


def _required_regular_file(root: Path, relative: str, max_bytes: int) -> Path:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise PackageValidationError(f"required regular file is missing: {relative}")
    if path.stat().st_size > max_bytes:
        raise PackageValidationError(f"required file exceeds size limit: {relative}")
    return path


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PackageValidationError(f"invalid JSON file: {path.name}") from exc


def _decode_json(name: str, payload: bytes) -> object:
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PackageValidationError(f"invalid JSON file: {name}") from exc


def _load_hash_index(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        raise PackageValidationError("source-hashes.sha256 must be ASCII text") from exc
    result: dict[str, str] = {}
    for line_number, line in enumerate(lines, start=1):
        if not line or "  " not in line:
            raise PackageValidationError(f"invalid hash index line {line_number}")
        digest, relative = line.split("  ", 1)
        if not _SHA256_RE.fullmatch(digest) or relative in result:
            raise PackageValidationError(f"invalid hash index line {line_number}")
        try:
            PackageFile.validate_relative_path(relative)
        except ValueError as exc:
            raise PackageValidationError(f"invalid hash index path on line {line_number}") from exc
        result[relative] = digest
    return result


def _reject_private_material(name: str, payload: bytes) -> None:
    try:
        text = payload.decode("utf-8")
    except UnicodeError as exc:
        raise PackageValidationError(f"declared text file is not UTF-8: {name}") from exc
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            raise PackageValidationError(f"possible secret detected in package file: {name}")
    if _PRIVATE_PATH_RE.search(text):
        raise PackageValidationError(f"absolute private path detected in package file: {name}")


def _validate_cross_references(
    manifest: EvidencePackageManifest,
    evidence: EvidenceBundle,
    provenance: PackageProvenance,
) -> None:
    if evidence.module_id != manifest.module_id or evidence.case_id != manifest.case_id:
        raise PackageValidationError("manifest and evidence identify different module/case values")
    if provenance.source_run_id != manifest.run_id:
        raise PackageValidationError("manifest and provenance identify different run values")
    if provenance.display != evidence.provenance:
        raise PackageValidationError("public provenance does not match the provenance document")

    for label, identifiers in (
        ("metric", [item.id for item in evidence.metrics]),
        ("artifact", [item.id for item in evidence.artifacts]),
        ("reference", [item.id for item in evidence.references]),
    ):
        if len(identifiers) != len(set(identifiers)):
            raise PackageValidationError(f"duplicate {label} IDs are not allowed")

    reference_ids = {item.id for item in evidence.references}
    package_files = {item.path: item for item in manifest.files}
    for reference in evidence.references:
        if reference.url:
            parsed = urlparse(reference.url)
            if parsed.scheme != "https" or not parsed.netloc:
                raise PackageValidationError(f"method reference URL must use HTTPS: {reference.id}")
    for artifact in evidence.artifacts:
        parsed = urlparse(artifact.href)
        if parsed.scheme and parsed.scheme != "https":
            raise PackageValidationError(f"artifact URL uses a forbidden scheme: {artifact.id}")
        if ".." in PurePosixPath(parsed.path).parts:
            raise PackageValidationError(f"artifact path traversal is forbidden: {artifact.id}")
        if manifest.publication_scope == "public" and not artifact.rights.strip():
            raise PackageValidationError(f"public artifact lacks rights metadata: {artifact.id}")
        if artifact.package_path:
            try:
                PackageFile.validate_relative_path(artifact.package_path)
            except ValueError as exc:
                raise PackageValidationError(
                    f"artifact has an invalid package path: {artifact.id}"
                ) from exc
            package_file = package_files.get(artifact.package_path)
            if package_file is None or package_file.role != "artifact":
                raise PackageValidationError(
                    f"artifact payload is not declared with the artifact role: {artifact.id}"
                )
            if artifact.sha256 != package_file.sha256:
                raise PackageValidationError(
                    f"artifact evidence hash does not match its payload: {artifact.id}"
                )
        elif manifest.publication_scope == "public" and artifact.kind in {"image", "video"}:
            raise PackageValidationError(
                f"public media artifact is not bound to a package payload: {artifact.id}"
            )
    if not reference_ids and manifest.module_id == "cfd":
        raise PackageValidationError("public CFD evidence must declare its method references")
