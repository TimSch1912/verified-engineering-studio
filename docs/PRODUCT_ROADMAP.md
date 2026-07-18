# Verified Engineering Studio product roadmap

Status: 2026-07-18

## Product thesis

Verified Engineering Studio (VES) is an evidence workbench for engineers. It does not replace a
solver, simulator, experiment or engineering sign-off. It turns their outputs into immutable,
traceable evidence packages; runs discipline-owned deterministic checks; and uses GPT-5.6 to
explain the resulting evidence without allowing the model to overrule those checks.

The first durable product has two equal verticals:

- **CFD:** OpenFOAM case evidence, force histories, mesh quality, uncertainty and grid convergence.
- **Isaac Sim:** task intent, skill plan, capability gate, execution trace, safety metrics and visual
  proof.

The public competition site remains a curated, read-only showcase. A separate private workspace
will become the daily engineering tool after the competition.

## Core architecture

```text
OpenFOAM case / Isaac run / generic export
                  │
                  ▼
          domain import adapter
                  │
                  ▼
      immutable VES Evidence Package
                  │
         ┌────────┴────────┐
         ▼                 ▼
 deterministic rules   artifact viewers
         │                 │
         └────────┬────────┘
                  ▼
       structured GPT-5.6 review
                  │
                  ▼
     engineer report + human decision
```

The shared core owns integrity, storage, provenance, review and reporting. Domain modules own
parsing, engineering checks, comparison logic and specialized views. The two verticals must not
import or mutate each other's source applications.

### Durable object model

1. **Project** — an engineering objective such as Laurons II resistance or G1 pick-and-place.
2. **Case** — a geometry, scenario or experimental configuration.
3. **Run** — one immutable solver or simulator execution.
4. **Evidence item** — scalar, time series, distribution, artifact, claim or limitation.
5. **Check result** — a deterministic, versioned computation over evidence.
6. **Review** — a derived AI or human interpretation that can be regenerated.
7. **Decision record** — an explicit human disposition, never an AI-generated approval.

Raw evidence and derived conclusions remain separate. Changing a parser, threshold, prompt or model
creates a new derived result; it never rewrites the original run.

## VES Evidence Package (`.vespack`)

Both domains will export the same portable package contract. The first implementation can be a
directory; a validated ZIP transport can follow.

```text
example.vespack/
├── manifest.json
├── evidence.json
├── provenance.json
├── timeseries/
├── artifacts/
└── source-hashes.sha256
```

Required properties:

- stable package, project, case and run IDs;
- schema and adapter versions;
- producer, solver/simulator version and creation time;
- SI value plus explicit unit and optional uncertainty for numerical evidence;
- SHA-256 for every source and artifact;
- explicit claims, limitations and publication rights;
- domain metadata under a namespaced extension field;
- no executable files, secrets, absolute private paths or implicit network access.

A `ves pack validate` command will verify structure, hashes, units, size limits, IDs and referenced
artifacts before an import is accepted.

## Product surfaces

### 1. Public showcase

- no account and no side effects;
- curated publishable cases only;
- cached guided reviews so the demonstration remains reliable and affordable;
- downloadable sanitized evidence/report, not protected raw project material;
- explicit `ready`, `preview`, `review required` and `blocked` states.

### 2. Private engineering workspace

- authenticated projects, cases and runs;
- upload/import, compare, annotate and report workflows;
- private source paths and unpublished artifacts never exposed publicly;
- human decision records and an audit history;
- any future execution action requires a proposal, explicit approval and a separate runner.

### 3. CLI and adapter SDK

Planned commands:

```text
ves pack validate <bundle>
ves import openfoam <case-or-export>
ves import isaac <run-export>
ves compare <run-a> <run-b> [<run-c>]
ves review <run-or-comparison>
ves report <run-or-comparison> --format html|markdown
```

The CLI and web application use the same Python services and schemas, so calculations cannot drift
between interfaces.

## CFD vertical

### Import

The OpenFOAM adapter will accept a curated export first and later a local read-only case path. It
will parse, where present:

- case and solver metadata, physical models and boundary-condition summary;
- cell count, patch inventory and `checkMesh` quality values;
- force and force-coefficient histories including patch decompositions;
- residual, continuity, Courant, time-step, volume and y-plus evidence;
- mesh images, wave renders, CAD renders and videos with publication metadata;
- reference values and their configuration/rights context.

### Deterministic engineering checks

- total-force decomposition and patch-balance closure;
- finite values, consistent sign convention and unit normalization;
- startup exclusion, stationarity and sampling-uncertainty diagnostics;
- mesh topology/quality, Courant, continuity and volume-conservation gates;
- wall-treatment/y-plus checks with wet/dry aggregation stated explicitly;
- comparison to the matching reference configuration without calibration to the target;
- three-grid classification, representative `h`, actual refinement ratios, observed order,
  Richardson extrapolation, `GCI21`, `GCI32` and asymptotic-range check;
- explicit handling of oscillatory/non-monotonic convergence and uncertainty overlap.

### Engineer experience

- case matrix across geometry and grid levels;
- synchronized force history, mesh/wave media and validation timeline;
- component waterfall and reference-deviation views;
- grid-convergence worksheet with every intermediate quantity visible;
- one-click evidence report suitable for the CFD presentation and later project documentation.

The current v9 result is useful even before the grid study is complete: VES can show that force
closure passes while discretization uncertainty remains open.

## Isaac Sim vertical

### Import

The Isaac adapter will consume a stable, read-only handoff export rather than importing the active
Bachelor-project source tree. The package can contain:

- task intent and clarification result;
- scene specification and object/zone identities;
- parameterized skill plan and symbolic replay;
- capability-gate result (`planning_only`, `live_verified` or `blocked`);
- execution contract and source/checkpoint/runtime hashes;
- per-run success, timeout, force, contact, collision and trajectory metrics;
- controller/seed comparison statistics;
- synchronized success/failure video, trace and telemetry artifacts.

### Deterministic engineering checks

- schema and hash-chain integrity across intent, scene, plan, contract and run;
- plan preconditions/postconditions and allowlisted skill IDs;
- live authority only for a proven executor binding;
- success definition, reset boundary and first-episode measurement integrity;
- contact, force, collision, clearance, timeout and non-finite safety gates;
- paired controller comparison with confidence intervals and declared stop rules;
- separation of simulated proof, visual demonstration and hardware/Sim2Real claims.

### Engineer experience

- pipeline view: prompt → intent → skill plan → capability gate → runtime → evidence;
- run timeline with video synchronized to stages, contacts, forces and failure events;
- baseline/candidate comparison across seeds and termination taxonomy;
- an evidence-backed release card explaining why a controller was retained or rejected;
- later, a private proposal-and-approval console for already proven capabilities only.

The public module must never directly command Isaac, a robot or paid compute. Runtime actions remain
in the existing fail-closed Isaac/MCP infrastructure and are integrated only after a stable handoff.

## AI review design

- GPT receives normalized evidence and deterministic check results, not unrestricted filesystem,
  shell, solver or actuator access.
- Pydantic Structured Outputs remain the contract for findings, caveats, next actions and exact
  evidence references.
- Application code removes unknown references and deterministically clamps the final status.
- Review modes will be `assess`, `compare`, `explain failure` and `draft report`; every mode uses the
  same evidence boundary.
- Prompt version, model, model snapshot when available, evidence hash, cache state and token usage
  are recorded.
- Golden CFD and Isaac fixtures will form an evaluation suite before prompts or model versions are
  changed.
- Optional PDF/image inputs may assist private exploratory review, but parsed numerical evidence
  remains authoritative and visual model interpretation is labelled advisory.

This follows OpenAI's current guidance to use Structured Outputs for schema adherence and to pin
production behavior with model snapshots plus evaluations:

- https://developers.openai.com/api/docs/guides/structured-outputs
- https://developers.openai.com/api/docs/guides/text#prompt-engineering
- https://developers.openai.com/api/docs/guides/file-inputs

## Implementation phases

### Phase 0 — competition release (18–21 July 2026)

Objective: one complete, credible dual-domain product story without destabilizing either source
project.

- add three guided, pre-cached CFD review questions;
- regenerate the live GPT-5.6 screenshot and harden the anonymous judge path;
- replace the Isaac placeholder only if the separate session supplies a stable handoff package;
- otherwise keep Isaac honestly marked as a read-only preview and omit unproven claims;
- add a Build Week development log, CI, judge instructions and final Devpost text;
- create a sub-three-minute narrated demo and submit early.

Exit gate: public demo, repository, media, video and submission agree on the same observed behavior.

### Phase 1 — evidence foundation (22–24 July 2026)

Objective: turn the showcase into a usable local engineering workbench.

- implement the `.vespack` schemas, validator and CLI;
- add SQLite metadata plus a content-addressed artifact directory;
- preserve immutable source/derived-result separation;
- implement projects, cases, runs and import history in the API/UI;
- produce deterministic HTML/Markdown reports;
- migrate the existing curated CFD case through the real importer.

Exit gate: deleting the current hard-coded case data and re-importing the package reproduces the
same checks and evidence hash.

### Phase 2 — both degree-project verticals (25–30 July 2026)

Objective: directly support the CFD presentation and G1 Bachelor-project evidence workflow.

- CFD: ingest the fine and available coarser grids, compute convergence/uncertainty, and export the
  final comparison report and figures;
- Isaac: ingest the stable handoff, implement trace/safety/comparison views, and export a run review;
- add cross-run annotation, decision records and publication-safe report profiles;
- verify all formulas against independent fixtures and show intermediate values.

Exit gate: each vertical can create a report from an exported source bundle without manual JSON
editing or access to the source application's code.

### Phase 3 — durable private studio (August 2026)

Objective: make VES the normal entry point for reviewing new engineering runs.

- authentication and strict public/private project separation;
- upload quotas, backup/restore and retention controls;
- richer time-series and synchronized media viewers;
- saved comparisons, annotations and human approvals;
- monitoring, CI releases, schema migrations and disaster-recovery tests;
- read-only connector to the Laurons live dashboard and stable Isaac export endpoint.

Exit gate: a new run can be imported, checked, reviewed, compared and reported without a code
change.

### Phase 4 — controlled automation and new disciplines

- proposal/approval workflow for private solver or simulator jobs;
- isolated runners with budget, timeout and cancellation guards;
- FEA and experimental/test-rig adapters;
- signed module manifests and a documented module SDK;
- optional organization/multi-user deployment only when a real need appears.

## What Codex can implement autonomously

- all VES core schemas, storage, API, UI, CLI, report generation and migrations;
- package integrity, provenance, caching, rate limiting, authentication and deployment;
- OpenFOAM/Isaac importers against supplied stable fixtures;
- deterministic formulas, statistical routines and reproducible unit tests;
- AI review prompts, Structured Output models, golden evals and cost controls;
- CI, documentation, screenshots, architecture graphics and the video script/editing pipeline;
- compatibility adapters without writing into the active CFD or Isaac source projects.

## Inputs and decisions that cannot be invented

- actual new CFD solver outputs and actual Isaac execution results;
- a stable Isaac handoff contract from the active development session;
- authoritative configuration matching and engineering thresholds where the source does not define
  them;
- permission to publish a specific artifact, reference or protected project detail;
- human acceptance/sign-off and any command that starts paid compute or physical execution;
- the final public YouTube upload and Devpost submission action.

## Product principles and non-goals

1. Evidence before confidence.
2. Domain rules outrank model prose.
3. Missing evidence is a result, not an invitation to hallucinate.
4. Public mode is read-only; private actions require proposal and approval.
5. One stable package boundary is preferable to coupling mature applications.
6. No claim of certification, hardware safety or grid independence without its defined evidence.
7. Keep FastAPI, Pydantic, SQLite and the dependency-light frontend until measured needs justify a
   rewrite or distributed database.

## Success measures

- every displayed claim links to an evidence/check ID;
- every imported source/artifact is hash-addressed and integrity-checkable;
- identical packages reproduce identical deterministic checks;
- corrupted or incomplete evidence fails closed without a model call;
- a new module requires an adapter and validators, not a review-core rewrite;
- CFD and Isaac each support import → checks → review → report end to end;
- the public judge path works without login and the private path exposes no unpublished material;
- AI prompt/model upgrades are blocked unless the golden evaluation suite remains green.
