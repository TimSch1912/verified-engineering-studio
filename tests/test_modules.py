from ves.core.registry import ModuleRegistry
from ves.modules.cfd import CFDModule
from ves.modules.isaac import IsaacModule


def test_registry_exposes_unique_modules():
    registry = ModuleRegistry()
    registry.register(CFDModule())
    registry.register(IsaacModule())
    assert [item.id for item in registry.descriptors()] == ["cfd", "isaac"]


def test_cfd_evidence_and_checks_are_reproducible():
    module = CFDModule()
    evidence = module.build_evidence("laurons-v9")
    values = {metric.id: metric.value for metric in evidence.metrics}
    assert values["metric.total_resistance"] == 48.19
    assert values["metric.period_mean"] == 49.36
    assert values["metric.cells"] == 3.91
    checks = {check.id: check for check in module.validate(evidence)}
    assert checks["check.force_decomposition"].status == "pass"
    assert checks["check.reference_delta"].status == "pass"
    assert checks["check.grid_convergence"].status == "warn"


def test_unknown_cfd_case_fails_closed():
    module = CFDModule()
    try:
        module.build_evidence("missing")
    except KeyError:
        pass
    else:
        raise AssertionError("Unknown cases must not fall back to a different evidence bundle")


def test_isaac_preview_is_a_stable_snapshot():
    module = IsaacModule()
    first = module.build_evidence("skill-plan-proof")
    second = module.build_evidence("skill-plan-proof")
    assert first.model_dump_json() == second.model_dump_json()
