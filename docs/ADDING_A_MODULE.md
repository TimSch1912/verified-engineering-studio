# Adding an engineering module

VES modules are deliberately small and read-only by default. A new discipline should be possible
without editing the review service or frontend routing.

## Required contract

Create a package under `src/ves/modules/<module_id>/` and implement `EngineeringModule`:

1. `describe()` returns stable metadata and capabilities.
2. `list_cases()` exposes curated, judge-testable cases.
3. `review_prompts()` returns guided, discipline-owned review questions.
4. `build_evidence(case_id)` returns `ves.evidence.v1`.
5. `validate(evidence)` runs deterministic, discipline-owned checks.

Register one instance in `ves.app`. Duplicate IDs fail during startup.

## Evidence rules

- Give every metric, artifact and check a stable ID.
- Record where each value came from and when it was produced.
- Keep case evidence separate from method references; a source can justify a rule without proving a
  run-specific fact.
- State limitations explicitly.
- Prefer aggregate, publishable fixtures over live access to private engineering systems.
- Do not give GPT access to a shell, solver or actuator merely to create a review.
- A failed deterministic check must not be softened by the model response.

Production adapters should consume a validated `.vespack` rather than read arbitrary source trees.
See [VES Evidence Package v1](VESPACK.md). The source application owns execution; the public module
owns only the read-only evidence adapter.

## Optional actions

Future private deployments may add side-effecting actions. Those actions belong behind a separate
capability, explicit user approval, authentication and an audit log. They are outside the public
Build Week scope.
