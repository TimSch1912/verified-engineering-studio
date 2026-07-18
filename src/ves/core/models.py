from __future__ import annotations

from datetime import datetime
from typing import Literal
from unicodedata import normalize

from pydantic import BaseModel, Field, field_validator

ModuleState = Literal["ready", "preview", "handoff_pending"]
CheckStatus = Literal["pass", "warn", "fail", "info"]
VerdictStatus = Literal["verified", "review", "blocked"]
FallbackReason = Literal[
    "not_configured",
    "client_limit",
    "daily_limit",
    "busy",
    "guard_error",
    "api_error",
]


class ModuleDescriptor(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]+$")
    version: str
    title: str
    short_title: str
    description: str
    discipline: str
    icon: str
    accent: str
    state: ModuleState
    capabilities: list[str]


class CaseDescriptor(BaseModel):
    id: str
    title: str
    summary: str
    state: Literal["ready", "preview"]


class Metric(BaseModel):
    id: str
    label: str
    value: float | str
    unit: str
    display: str
    source: str


class EvidenceArtifact(BaseModel):
    id: str
    title: str
    kind: Literal["image", "video", "link"]
    href: str
    caption: str
    rights: str


class EvidenceBundle(BaseModel):
    schema_version: Literal["ves.evidence.v1"] = "ves.evidence.v1"
    module_id: str
    case_id: str
    case_title: str
    generated_at: datetime
    metrics: list[Metric]
    artifacts: list[EvidenceArtifact]
    claims: list[str]
    limits: list[str]
    provenance: dict[str, str]


class ValidationCheck(BaseModel):
    id: str
    status: CheckStatus
    title: str
    detail: str
    evidence_refs: list[str]


class Finding(BaseModel):
    severity: Literal["positive", "attention", "critical"]
    title: str
    detail: str
    evidence_refs: list[str]


class EngineeringVerdict(BaseModel):
    status: VerdictStatus
    summary: str
    findings: list[Finding]
    caveats: list[str]
    next_actions: list[str]
    evidence_refs: list[str]


class ReviewRequest(BaseModel):
    module_id: str
    case_id: str
    question: str = Field(min_length=3, max_length=800)

    @field_validator("question", mode="before")
    @classmethod
    def normalize_question(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return " ".join(normalize("NFC", value).split())


class ReviewProvenance(BaseModel):
    generated_at: datetime
    mode: Literal["gpt-5.6", "deterministic-fallback"]
    model: str
    evidence_sha256: str
    schema_version: Literal["ves.review.v1"] = "ves.review.v1"
    api_error: bool = False
    cache_hit: bool = False
    live_api_call: bool = False
    fallback_reason: FallbackReason | None = None


class ReviewEnvelope(BaseModel):
    verdict: EngineeringVerdict
    checks: list[ValidationCheck]
    evidence: EvidenceBundle
    provenance: ReviewProvenance


class ReviewAvailability(BaseModel):
    api_configured: bool
    live_ai_available: bool
    deterministic_fallback_available: Literal[True] = True
    reason: FallbackReason | None = None
    model: str
    max_output_tokens: int
    cache_enabled: Literal[True] = True
