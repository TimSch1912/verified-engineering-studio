# CFD method basis

VES separates two kinds of support:

- **case evidence** records what a specific run produced;
- **method references** explain why a deterministic check or calculation is appropriate.

A textbook can support a method, but it cannot prove that a particular mesh, force value or solver
run is correct. The review layer is instructed to preserve this boundary.

## Primary textbook

H. K. Versteeg and W. Malalasekera, *An Introduction to Computational Fluid Dynamics: The Finite
Volume Method*, 2nd edition, Pearson, 2007, ISBN 978-0-13-127498-3.

The implementation uses the following sections. Printed page numbers are followed by PDF page
numbers for the local 517-page edition supplied for this project.

| Topic used by VES | Textbook location | Product consequence |
|---|---|---|
| Error versus uncertainty; numerical, input and model contributions | Chapter 10, pp. 285–291 (PDF pp. 299–305) | VES reports open error/uncertainty sources instead of reducing quality to one score. |
| Residuals and iterative convergence | pp. 287–289 (PDF pp. 301–303) | Residuals are evidence, but target quantities must also be tested against tighter stopping criteria. |
| Verification versus validation | pp. 293–296 (PDF pp. 307–310) | A mesh study verifies numerical behavior; comparison with experimental data addresses validation. The terms are not interchangeable. |
| Conditions for Richardson/GCI use | pp. 294–295 (PDF pp. 308–309) | The current calculator requires a smooth, monotonic, approximately constant-ratio three-grid sequence. |
| Observed order and GCI safety factor | p. 295 (PDF p. 309) | With three successive grids, VES uses observed order and the stated 1.25 safety factor. It refuses to calculate when the prerequisites fail. |
| Best practice and building-block approach | pp. 298–299 (PDF pp. 312–313) | Complex workflows are split into independently checkable modules and evidence gates. |
| Reproducible CFD documentation | pp. 300–301 (PDF pp. 314–315) | The package records geometry, models, mesh, time controls, schemes and convergence settings when supplied, and lists missing fields explicitly. |
| Conservation and plausibility checks | pp. 301–302 (PDF pp. 315–316) | Force/patch closure and later mass, momentum, volume and continuity checks are deterministic gates. |

No textbook content is redistributed in this repository. Citations and short method summaries are
stored in the evidence package; the source PDF remains outside Git.

## Complementary procedure

The grid-study plan also uses ITTC Recommended Procedures and Guidelines 7.5-03-01-01,
*Uncertainty Analysis in CFD — Verification and Validation Methodology and Procedures*, Revision
03, 2017. It supports systematic parameter refinement, convergence classification and uncertainty
reporting for marine CFD.

The first calculator intentionally implements only the constant-ratio, monotonic three-grid case
covered directly by the textbook. A ratio-spread tolerance of 5% is a conservative VES software
policy, not a threshold stated by Versteeg and Malalasekera. Materially unequal refinement ratios,
oscillatory behavior, divergence or negligible solution differences return no GCI. A generalized
unequal-ratio implementation will be added with independent reference fixtures before use.

## Current formula boundary

For an unchanged three-dimensional domain, representative cell size is approximated by

\[
h \propto N^{-1/3},
\]

so the effective refinement ratios are calculated from the actual cell counts:

\[
r_{21}=\left(\frac{N_1}{N_2}\right)^{1/3},\qquad
r_{32}=\left(\frac{N_2}{N_3}\right)^{1/3},
\]

with indices 1 = fine, 2 = medium and 3 = coarse. For a valid constant-ratio monotonic sequence,
the observed order is

\[
p=\frac{\ln\left|\left(\phi_3-\phi_2\right)/\left(\phi_2-\phi_1\right)\right|}{\ln r}.
\]

VES then reports the Richardson-extrapolated value, fine-grid error estimate, `GCI21`, `GCI32` and
the asymptotic-ratio diagnostic. Discretization uncertainty is kept separate from time-sampling,
iterative, input, model and experimental uncertainty.

Run the transparent calculator with:

```bash
ves cfd convergence \
  --fine-value <phi1> --medium-value <phi2> --coarse-value <phi3> \
  --fine-cells <N1> --medium-cells <N2> --coarse-cells <N3> --json
```
