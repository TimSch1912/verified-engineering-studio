from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ves.core.models import (
    CaseDescriptor,
    EvidenceArtifact,
    EvidenceBundle,
    Metric,
    ModuleDescriptor,
    ValidationCheck,
)
from ves.modules.base import EngineeringModule


class CFDModule(EngineeringModule):
    _case_path = Path(__file__).with_name("case_v9.json")

    def describe(self) -> ModuleDescriptor:
        return ModuleDescriptor(
            id="cfd",
            version="0.1.0",
            title="CFD Evidence Review",
            short_title="CFD",
            description="Audit resistance results, numerical evidence and validation gaps.",
            discipline="Computational fluid dynamics",
            icon="≈",
            accent="#35d1bd",
            state="ready",
            capabilities=["evidence", "deterministic-validation", "gpt-review", "media"],
        )

    def list_cases(self) -> list[CaseDescriptor]:
        return [
            CaseDescriptor(
                id="laurons-v9",
                title="Laurons II · v9",
                summary="Full hull, keel and two-rudder resistance run with 3.91 M cells.",
                state="ready",
            )
        ]

    def build_evidence(self, case_id: str) -> EvidenceBundle:
        if case_id != "laurons-v9":
            raise KeyError(case_id)
        raw = json.loads(self._case_path.read_text(encoding="utf-8"))
        return EvidenceBundle(
            module_id="cfd",
            case_id=raw["case_id"],
            case_title=raw["case_title"],
            generated_at=datetime.fromisoformat(raw["generated_at"].replace("Z", "+00:00")),
            metrics=[Metric.model_validate(item) for item in raw["metrics"]],
            artifacts=[EvidenceArtifact.model_validate(item) for item in raw["artifacts"]],
            claims=raw["claims"],
            limits=raw["limits"],
            provenance=raw["provenance"],
        )

    def validate(self, evidence: EvidenceBundle) -> list[ValidationCheck]:
        values = {metric.id: metric.value for metric in evidence.metrics}
        total = float(values["metric.total_resistance"])
        pressure_friction = float(values["metric.pressure"]) + float(values["metric.friction"])
        patches = (
            float(values["metric.hull"])
            + float(values["metric.keel"])
            + float(values["metric.rudders"])
        )
        period = float(values["metric.period_mean"])
        reference = float(values["metric.reference_resistance"])
        stored_delta = float(values["metric.period_delta"])
        calculated_delta = 100.0 * (period - reference) / reference

        return [
            ValidationCheck(
                id="check.force_decomposition",
                status="pass" if abs(pressure_friction - total) <= 0.02 else "fail",
                title="Force decomposition closes",
                detail=(
                    f"Pressure + friction = {pressure_friction:.2f} N; "
                    f"reported total = {total:.2f} N."
                ),
                evidence_refs=[
                    "metric.pressure",
                    "metric.friction",
                    "metric.total_resistance",
                ],
            ),
            ValidationCheck(
                id="check.patch_balance",
                status="pass" if abs(patches - total) <= 0.5 else "warn",
                title="Patch contributions are consistent within reporting precision",
                detail=f"Hull + keel + rudders = {patches:.2f} N versus {total:.2f} N total.",
                evidence_refs=["metric.hull", "metric.keel", "metric.rudders"],
            ),
            ValidationCheck(
                id="check.reference_delta",
                status="pass" if abs(calculated_delta - stored_delta) <= 0.02 else "fail",
                title="Reference deviation is reproducible",
                detail=f"Recalculated deviation = {calculated_delta:.2f} %.",
                evidence_refs=[
                    "metric.period_mean",
                    "metric.reference_resistance",
                    "metric.period_delta",
                ],
            ),
            ValidationCheck(
                id="check.grid_convergence",
                status="warn",
                title="Discretization uncertainty remains open",
                detail=(
                    "The fine run is available, but two systematically coarser grids are pending."
                ),
                evidence_refs=["metric.cells"],
            ),
        ]
