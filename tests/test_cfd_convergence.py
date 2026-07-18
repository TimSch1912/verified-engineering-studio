import json

import pytest

from ves.cli import main
from ves.modules.cfd.convergence import (
    analyze_three_grid_sequence,
    representative_refinement_ratio,
)


def test_representative_ratio_applies_to_cell_size_not_cell_count():
    ratio = representative_refinement_ratio(3_910_000, 1_382_394)
    assert ratio == pytest.approx(2**0.5, rel=2e-4)


def test_uniform_monotonic_sequence_reports_observed_order_and_gci():
    result = analyze_three_grid_sequence(
        fine_value=99.0,
        medium_value=100.0,
        coarse_value=102.0,
        fine_cells=2_828_427,
        medium_cells=1_000_000,
        coarse_cells=353_553,
    )

    assert result.classification == "monotonic_convergence"
    assert result.r21 == pytest.approx(2**0.5, rel=1e-6)
    assert result.r32 == pytest.approx(2**0.5, rel=1e-6)
    assert result.observed_order == pytest.approx(2.0, rel=1e-5)
    assert result.extrapolated_value == pytest.approx(98.0, rel=1e-5)
    assert result.fine_discretization_error == pytest.approx(-1.0, rel=1e-5)
    assert result.gci21_percent == pytest.approx(1.262626, rel=1e-5)
    assert result.safety_factor == 1.25
    assert result.method_ref == "ref.versteeg2007.ch10"


@pytest.mark.parametrize(
    ("values", "cells", "classification"),
    [
        ((100.0, 101.0, 100.0), (2_828_427, 1_000_000, 353_553), "oscillatory"),
        (
            (100.0, 102.0, 103.0),
            (2_828_427, 1_000_000, 353_553),
            "monotonic_divergence",
        ),
        ((100.0, 101.0, 103.0), (8_000_000, 1_000_000, 500_000), "nonuniform_refinement"),
    ],
)
def test_invalid_gci_regimes_return_no_false_uncertainty(values, cells, classification):
    result = analyze_three_grid_sequence(
        fine_value=values[0],
        medium_value=values[1],
        coarse_value=values[2],
        fine_cells=cells[0],
        medium_cells=cells[1],
        coarse_cells=cells[2],
    )

    assert result.classification == classification
    assert result.gci21_percent is None
    assert result.extrapolated_value is None


def test_convergence_cli_is_machine_readable(capsys):
    exit_code = main(
        [
            "cfd",
            "convergence",
            "--fine-value",
            "99",
            "--medium-value",
            "100",
            "--coarse-value",
            "102",
            "--fine-cells",
            "2828427",
            "--medium-cells",
            "1000000",
            "--coarse-cells",
            "353553",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["classification"] == "monotonic_convergence"


def test_invalid_cell_order_is_rejected():
    with pytest.raises(ValueError, match="cell counts"):
        analyze_three_grid_sequence(
            fine_value=1.0,
            medium_value=2.0,
            coarse_value=3.0,
            fine_cells=100,
            medium_cells=100,
            coarse_cells=10,
        )
