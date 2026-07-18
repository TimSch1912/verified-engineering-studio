from __future__ import annotations

from pathlib import Path

from ves.core.models import (
    CaseDescriptor,
    EvidenceBundle,
    ModuleDescriptor,
    ReviewPrompt,
    ValidationCheck,
)
from ves.core.package import ValidatedEvidencePackage, validate_evidence_package
from ves.modules.base import EngineeringModule


class CFDModule(EngineeringModule):
    _case_path = Path(__file__).with_name("packages") / "laurons-v9.vespack"

    def describe(self) -> ModuleDescriptor:
        return ModuleDescriptor(
            id="cfd",
            version="0.2.0",
            title="CFD Evidence Review",
            short_title="CFD",
            description="Audit resistance results, numerical evidence and validation gaps.",
            discipline="Computational fluid dynamics",
            icon="≈",
            accent="#35d1bd",
            state="ready",
            capabilities=[
                "evidence-package",
                "hash-integrity",
                "deterministic-validation",
                "method-citations",
                "gpt-review",
            ],
        )

    def list_cases(self) -> list[CaseDescriptor]:
        package = self.load_package()
        return [
            CaseDescriptor(
                id="laurons-v9",
                title="Laurons II · v9",
                summary=(
                    "Hash-validated public package for the full hull, keel and two-rudder "
                    "resistance run with 3.91 M cells."
                ),
                state="ready",
                package_sha256=package.package_sha256,
            )
        ]

    def review_prompts(self) -> list[ReviewPrompt]:
        return [
            ReviewPrompt(
                id="support",
                label="Result support",
                question=(
                    "Assess whether the supplied evidence supports the reported resistance and "
                    "separate passed checks from open verification gaps."
                ),
            ),
            ReviewPrompt(
                id="grid-study",
                label="Grid study",
                question=(
                    "Explain exactly why this case is not yet grid-independent and define the "
                    "next three-grid verification steps without inventing missing values."
                ),
            ),
            ReviewPrompt(
                id="review-brief",
                label="Decision brief",
                question=(
                    "Draft a concise engineering decision brief covering force closure, the "
                    "reference comparison, limitations and the next defensible action."
                ),
            ),
        ]

    def build_evidence(self, case_id: str) -> EvidenceBundle:
        if case_id != "laurons-v9":
            raise KeyError(case_id)
        return self.load_package().evidence

    def load_package(self) -> ValidatedEvidencePackage:
        return validate_evidence_package(self._case_path)

    def validate(self, evidence: EvidenceBundle) -> list[ValidationCheck]:
        validated_source = self.load_package().evidence
        package_matches = evidence == validated_source
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
        documentation_fields = {
            "solver",
            "solver_version",
            "computing_platform",
            "geometry",
            "boundary_conditions",
            "initial_conditions",
            "fluid_properties",
            "turbulence_model",
            "mesh",
            "time_control",
            "numerical_schemes",
            "convergence_criteria",
        }
        missing_documentation = sorted(documentation_fields - evidence.provenance.keys())

        return [
            ValidationCheck(
                id="check.package_integrity",
                status="pass" if package_matches else "fail",
                title="Evidence package crossed the integrity gate",
                detail=(
                    "Manifest, payload schemas, file sizes, SHA-256 index, publication metadata "
                    "and privacy boundary were validated before this case was loaded."
                    if package_matches
                    else "The reviewed evidence differs from the validated package payload."
                ),
                evidence_refs=[],
            ),
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
                method_refs=["ref.versteeg2007.ch10"],
            ),
            ValidationCheck(
                id="check.patch_balance",
                status="pass" if abs(patches - total) <= 0.5 else "warn",
                title="Patch contributions are consistent within reporting precision",
                detail=f"Hull + keel + rudders = {patches:.2f} N versus {total:.2f} N total.",
                evidence_refs=["metric.hull", "metric.keel", "metric.rudders"],
                method_refs=["ref.versteeg2007.ch10"],
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
                    "Only the fine run is available. Two systematically coarser grids are still "
                    "required to establish observed order and discretization uncertainty."
                ),
                evidence_refs=["metric.cells"],
                method_refs=["ref.versteeg2007.ch10", "ref.ittc2017.vv"],
            ),
            ValidationCheck(
                id="check.reproduction_documentation",
                status="warn" if missing_documentation else "pass",
                title="Public package is not yet reproduction-complete",
                detail=(
                    "Missing from the sanitized archive: "
                    + ", ".join(missing_documentation)
                    + ". These fields are not invented; they must come from the source case export."
                    if missing_documentation
                    else "The documented CFD input and solution fields are complete."
                ),
                evidence_refs=[],
                method_refs=["ref.versteeg2007.ch10"],
            ),
        ]
