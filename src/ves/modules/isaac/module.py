from __future__ import annotations

from datetime import UTC, datetime

from ves.core.models import (
    CaseDescriptor,
    EvidenceArtifact,
    EvidenceBundle,
    Metric,
    ModuleDescriptor,
    ValidationCheck,
)
from ves.modules.base import EngineeringModule


class IsaacModule(EngineeringModule):
    """Read-only placeholder until the separate Isaac session hands over a stable snapshot."""

    def describe(self) -> ModuleDescriptor:
        return ModuleDescriptor(
            id="isaac",
            version="0.1.0",
            title="Robotics Skill Verification",
            short_title="Robotics",
            description="Trace an intent through skill planning, gates and execution evidence.",
            discipline="Robotics simulation",
            icon="◇",
            accent="#9b8cff",
            state="handoff_pending",
            capabilities=["intent", "skill-plan", "gates", "proof-link"],
        )

    def list_cases(self) -> list[CaseDescriptor]:
        return [
            CaseDescriptor(
                id="skill-plan-proof",
                title="Intent → skill plan → proof",
                summary="Stable handoff snapshot will replace this read-only preview.",
                state="preview",
            )
        ]

    def build_evidence(self, case_id: str) -> EvidenceBundle:
        if case_id != "skill-plan-proof":
            raise KeyError(case_id)
        return EvidenceBundle(
            module_id="isaac",
            case_id=case_id,
            case_title="Isaac Skill Studio · handoff preview",
            generated_at=datetime.now(UTC),
            metrics=[
                Metric(
                    id="metric.pipeline_stages",
                    label="Verified pipeline stages",
                    value=4,
                    unit="stages",
                    display="4 stages",
                    source="Existing generalized task pipeline",
                )
            ],
            artifacts=[
                EvidenceArtifact(
                    id="artifact.isaac_showcase",
                    title="Public Isaac Skill Studio",
                    kind="link",
                    href="https://isaac-sim.schares-timo.de/showcase",
                    caption="Existing public showcase; stable API handoff is pending.",
                    rights="Project-owned application",
                )
            ],
            claims=[
                "The existing pipeline separates task intent, skill planning, gates and execution.",
                (
                    "The competition module consumes a stable snapshot instead of changing the "
                    "Isaac app."
                ),
            ],
            limits=[
                (
                    "The active Isaac bug-fix session has not delivered its final handoff "
                    "protocol yet."
                ),
                "No robot or simulator action is triggered by this public review module.",
            ],
            provenance={
                "source": "Isaac Skill Studio public showcase and generalized task pipeline",
                "integration": "read-only adapter",
                "handoff": "pending",
            },
        )

    def validate(self, evidence: EvidenceBundle) -> list[ValidationCheck]:
        return [
            ValidationCheck(
                id="check.isaac_handoff",
                status="warn",
                title="Stable Isaac handoff pending",
                detail=(
                    "The adapter remains preview-only until the bug-fix session provides its "
                    "protocol."
                ),
                evidence_refs=["artifact.isaac_showcase"],
            ),
            ValidationCheck(
                id="check.read_only_boundary",
                status="pass",
                title="Public module is read-only",
                detail="The current adapter cannot issue simulator or robot commands.",
                evidence_refs=["metric.pipeline_stages"],
            ),
        ]
