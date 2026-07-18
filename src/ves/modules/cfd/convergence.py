from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Literal

ConvergenceClass = Literal[
    "monotonic_convergence",
    "monotonic_divergence",
    "oscillatory",
    "indeterminate",
    "nonuniform_refinement",
]


@dataclass(frozen=True)
class GridConvergenceResult:
    classification: ConvergenceClass
    fine_value: float
    medium_value: float
    coarse_value: float
    fine_cells: int
    medium_cells: int
    coarse_cells: int
    r21: float
    r32: float
    observed_order: float | None
    extrapolated_value: float | None
    fine_discretization_error: float | None
    gci21_percent: float | None
    gci32_percent: float | None
    asymptotic_ratio: float | None
    safety_factor: float | None
    method_ref: str
    note: str

    def as_dict(self) -> dict[str, float | int | str | None]:
        return asdict(self)


def representative_refinement_ratio(
    finer_cells: int,
    coarser_cells: int,
    *,
    dimensions: int = 3,
) -> float:
    """Approximate h_coarse / h_fine for an unchanged domain volume."""

    if dimensions < 1:
        raise ValueError("dimensions must be positive")
    if finer_cells <= coarser_cells or coarser_cells <= 0:
        raise ValueError("finer_cells must be greater than positive coarser_cells")
    return (finer_cells / coarser_cells) ** (1.0 / dimensions)


def analyze_three_grid_sequence(
    *,
    fine_value: float,
    medium_value: float,
    coarse_value: float,
    fine_cells: int,
    medium_cells: int,
    coarse_cells: int,
    dimensions: int = 3,
    uniform_ratio_tolerance: float = 0.05,
    zero_tolerance: float = 1e-12,
) -> GridConvergenceResult:
    """Evaluate a uniform, monotonic three-grid sequence and fail closed otherwise.

    Indices follow the common convention 1=fine, 2=medium, 3=coarse. The observed-order and
    GCI calculation follows Versteeg & Malalasekera (2007), Chapter 10, for a constant refinement
    ratio and three successive grids. Statistical/time-sampling uncertainty is deliberately not
    folded into this discretization estimate.
    """

    values = (fine_value, medium_value, coarse_value)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("grid values must be finite")
    if not fine_cells > medium_cells > coarse_cells > 0:
        raise ValueError("cell counts must decrease from fine to medium to coarse")
    if not 0 <= uniform_ratio_tolerance < 1:
        raise ValueError("uniform_ratio_tolerance must be in [0, 1)")
    if zero_tolerance <= 0:
        raise ValueError("zero_tolerance must be positive")

    r21 = representative_refinement_ratio(fine_cells, medium_cells, dimensions=dimensions)
    r32 = representative_refinement_ratio(medium_cells, coarse_cells, dimensions=dimensions)
    ratio_spread = abs(r21 - r32) / ((r21 + r32) / 2.0)
    if ratio_spread > uniform_ratio_tolerance:
        return _empty_result(
            "nonuniform_refinement",
            values,
            (fine_cells, medium_cells, coarse_cells),
            r21,
            r32,
            (
                "The current constant-ratio method is not applicable. Use a generalized "
                "unequal-ratio procedure rather than averaging materially different ratios."
            ),
        )

    epsilon21 = medium_value - fine_value
    epsilon32 = coarse_value - medium_value
    scale = max(1.0, *(abs(value) for value in values))
    if abs(epsilon21) <= zero_tolerance * scale or abs(epsilon32) <= zero_tolerance * scale:
        return _empty_result(
            "indeterminate",
            values,
            (fine_cells, medium_cells, coarse_cells),
            r21,
            r32,
            "A zero or numerically negligible solution difference makes observed order undefined.",
        )
    if epsilon21 * epsilon32 < 0:
        return _empty_result(
            "oscillatory",
            values,
            (fine_cells, medium_cells, coarse_cells),
            r21,
            r32,
            "Successive solution changes reverse sign; the monotonic GCI formula is not applied.",
        )
    if abs(epsilon21) >= abs(epsilon32):
        return _empty_result(
            "monotonic_divergence",
            values,
            (fine_cells, medium_cells, coarse_cells),
            r21,
            r32,
            "The solution change does not decrease on refinement; no GCI is reported.",
        )

    refinement_ratio = math.sqrt(r21 * r32)
    observed_order = math.log(abs(epsilon32 / epsilon21)) / math.log(refinement_ratio)
    if not math.isfinite(observed_order) or observed_order <= 0:
        return _empty_result(
            "indeterminate",
            values,
            (fine_cells, medium_cells, coarse_cells),
            r21,
            r32,
            "The observed order is not a positive finite value; no GCI is reported.",
        )

    denominator21 = r21**observed_order - 1.0
    denominator32 = r32**observed_order - 1.0
    fine_error = (fine_value - medium_value) / denominator21
    extrapolated = fine_value + fine_error
    safety_factor = 1.25
    gci21 = _relative_gci(fine_value, medium_value, denominator21, safety_factor)
    gci32 = _relative_gci(medium_value, coarse_value, denominator32, safety_factor)
    asymptotic_ratio = None
    if gci21 is not None and gci21 > 0 and gci32 is not None:
        asymptotic_ratio = gci32 / (r21**observed_order * gci21)

    return GridConvergenceResult(
        classification="monotonic_convergence",
        fine_value=fine_value,
        medium_value=medium_value,
        coarse_value=coarse_value,
        fine_cells=fine_cells,
        medium_cells=medium_cells,
        coarse_cells=coarse_cells,
        r21=r21,
        r32=r32,
        observed_order=observed_order,
        extrapolated_value=extrapolated,
        fine_discretization_error=fine_error,
        gci21_percent=gci21,
        gci32_percent=gci32,
        asymptotic_ratio=asymptotic_ratio,
        safety_factor=safety_factor,
        method_ref="ref.versteeg2007.ch10",
        note=(
            "Constant-ratio three-grid estimate. Confirm mesh similarity, iterative convergence, "
            "time-step sensitivity and sampling uncertainty separately."
        ),
    )


def _relative_gci(
    finer_value: float,
    coarser_value: float,
    denominator: float,
    safety_factor: float,
) -> float | None:
    if finer_value == 0:
        return None
    approximate_relative_error = abs((finer_value - coarser_value) / finer_value)
    return 100.0 * safety_factor * approximate_relative_error / denominator


def _empty_result(
    classification: ConvergenceClass,
    values: tuple[float, float, float],
    cells: tuple[int, int, int],
    r21: float,
    r32: float,
    note: str,
) -> GridConvergenceResult:
    return GridConvergenceResult(
        classification=classification,
        fine_value=values[0],
        medium_value=values[1],
        coarse_value=values[2],
        fine_cells=cells[0],
        medium_cells=cells[1],
        coarse_cells=cells[2],
        r21=r21,
        r32=r32,
        observed_order=None,
        extrapolated_value=None,
        fine_discretization_error=None,
        gci21_percent=None,
        gci32_percent=None,
        asymptotic_ratio=None,
        safety_factor=None,
        method_ref="ref.versteeg2007.ch10",
        note=note,
    )
