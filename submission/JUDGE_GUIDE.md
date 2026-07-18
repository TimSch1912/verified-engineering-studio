# Judge guide — Verified Engineering Studio

No account is required. The public product is intentionally read-only.

## Fast path (about 90 seconds)

1. Open <https://verifiedengineeringstudio.schares-timo.de>.
2. In **CFD**, inspect the `evidence_package` provenance row and the open **Engineering method
   basis** section. The textbook supports the rules; the metric cards remain the run evidence.
3. Select **Result support** and run the review. The deterministic gates are rendered before the
   structured findings. Force closure passes, while grid convergence and reproduction
   documentation remain warnings; GPT cannot upgrade the result past `review`.
4. Select **Grid study** to see a review focused on the missing three-grid evidence. Successful
   identical live reviews are cached. If the public live budget is unavailable, the product says so
   and returns the cost-safe deterministic verdict rather than pretending GPT ran.
5. Switch to **Robotics**. Its `handoff pending` state is deliberate: the public adapter shows the
   cross-domain contract but makes no unproven execution claim and cannot command Isaac Sim.

## Repository proof

```bash
uv sync --frozen --extra test
uv run pytest -q
uv run ruff check .
uv run ves pack validate src/ves/modules/cfd/packages/laurons-v9.vespack
```

The package command verifies schemas, exact byte sizes, SHA-256 values, publication rights and the
privacy boundary before the CFD module can load.

## Scope boundary

- Pre-existing: Laurons II OpenFOAM v9 run and Isaac Skill Studio.
- Build Week: VES schemas, package boundary, adapters, deterministic gates, GPT-5.6 review layer,
  frontend, tests, deployment and documentation.
- Not claimed: CFD certification, completed grid independence, physical-robot proof or a stable
  Isaac handoff before its evidence package exists.
