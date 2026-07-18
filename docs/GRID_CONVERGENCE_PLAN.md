# Laurons II three-grid convergence plan

The v9 mesh is the existing fine grid with approximately 3.91 million cells. Building the sequence
from fine to coarse is practical, but the final analysis remains a grid convergence / discretization
uncertainty study.

## Refinement ratio

The refinement factor applies to representative cell size `h`, not directly to total cell count.
For a three-dimensional domain of unchanged volume, `h` scales approximately with `N^(-1/3)`.

For `r = h_coarse / h_fine = sqrt(2)`:

| Level | Target cells | Effective `h` ratio |
|---|---:|---:|
| Fine | 3.91 M | 1.000 |
| Medium | about 1.38 M | 1.414 |
| Coarse | about 0.49 M | 1.414 |

Simply dividing the cell count by `sqrt(2)` would produce an effective 3D refinement ratio of only
about 1.122. That is below the commonly recommended `r > 1.3` and is unlikely to separate the
discretization levels cleanly enough for a useful GCI estimate.

The target counts are estimates. After meshing, calculate the actual representative size and ratios
from the resulting cells; do not force a nominal cell count at the expense of mesh similarity.

## Controls that stay fixed

- geometry, domain, boundary conditions and physical models
- hull, keel and both rudders on every level
- solver schemes and convergence controls
- Courant constraints and physical simulation duration
- force definitions, sign conventions and averaging windows
- transient startup exclusion and period/block averaging method

Mesh controls should be coarsened systematically. Surface, free-surface and wake refinements, layer
resolution and feature capture must remain geometrically comparable. If the coarse target loses a
rudder, boundary layer or relevant wave structure, increase its resolution and use the actual unequal
refinement ratios in the analysis.

## Required outputs

For total resistance and the important components, report:

1. fine, medium and coarse time-averaged values with sampling uncertainty;
2. actual representative `h` and `r21`, `r32`;
3. monotonic or oscillatory convergence classification;
4. observed order `p`;
5. Richardson-extrapolated value;
6. `GCI21` and `GCI32` plus the asymptotic-range check;
7. comparison with the aggregate towing-test reference.

Three similar resistance values are encouraging, but they do not by themselves complete the study.
Their differences must be evaluated against transient/statistical uncertainty and the GCI procedure.

The first transparent calculator is available as `ves cfd convergence`. It computes a result only
for an approximately constant-ratio, monotonic three-grid sequence; all other regimes return no GCI
instead of a misleading number. See [CFD method basis](CFD_METHOD_REFERENCES.md) for its formula and
scope.

Primary method basis: H. K. Versteeg and W. Malalasekera, *An Introduction to Computational Fluid
Dynamics: The Finite Volume Method*, 2nd ed., Chapter 10, especially pp. 293–301. Complementary
procedure: ITTC 7.5-03-01-01, Revision 03 (2017). The later generalized unequal-ratio calculation
will be verified against I. B. Celik et al., *Procedure for Estimation and Reporting of Uncertainty
Due to Discretization in CFD Applications*, Journal of Fluids Engineering 130 (2008).
