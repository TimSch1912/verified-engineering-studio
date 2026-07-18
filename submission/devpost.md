# Devpost submission draft

## Project name

Verified Engineering Studio

## Elevator pitch

Evidence-first AI reviews for CFD and robotics. Deterministic checks stay in control while GPT-5.6 turns traceable data into cited verdicts and next actions.

## About the project

### Inspiration

Engineering AI often sounds confident before it has earned that confidence. A useful review must show which result came from a solver, which check was calculated deterministically, which limitation is still open, and which statement is only an AI interpretation.

We built Verified Engineering Studio (VES) around a simple principle: **evidence before confidence**. The model may explain and prioritize, but engineering gates remain authoritative.

### What it does

VES is a public, read-only review surface for engineering workflows. A user selects a discipline and a curated case, asks a review question, and receives:

- a typed evidence bundle with metrics, artifacts, sources and limitations;
- deterministic, discipline-specific validation checks;
- a structured GPT-5.6 verdict with findings, caveats and next actions;
- provenance including the model, schema version and SHA-256 evidence fingerprint.

The first two modules demonstrate that the same contract works across very different domains:

1. **CFD Evidence Review** audits a completed OpenFOAM resistance calculation for the reconstructed Roman merchant ship Laurons II. It checks force decomposition, patch balance and the deviation from an aggregate towing-test reference. It also refuses to call the result grid-independent because the three-grid convergence study is still pending.
2. **Robotics Skill Verification** previews how a task intent will map through skill planning, deterministic gates and execution proof from Isaac Skill Studio. It is honestly marked `handoff pending` until the separate stabilization session supplies a stable export; the public adapter cannot command the simulator.

The public app never starts a CFD solver, simulator or robot. GPT-5.6 reviews supplied evidence; it does not manufacture measurements or replace engineering sign-off.

### How we built it

The backend uses Python, FastAPI and Pydantic. Every engineering module implements five small methods:

```python
describe()        -> ModuleDescriptor
list_cases()      -> list[CaseDescriptor]
review_prompts()  -> list[ReviewPrompt]
build_evidence()  -> EvidenceBundle
validate()        -> list[ValidationCheck]
```

The CFD case now enters through a real directory-form `.vespack`. Before loading it, VES validates typed schemas, declared byte sizes, a SHA-256 file index, artifact rights and privacy rules; undeclared, executable, symlinked, path-traversing or secret-shaped content fails closed. The shared core then runs discipline-owned checks and hashes the exact normalized evidence payload.

The CFD method trail cites Versteeg & Malalasekera's finite-volume textbook for error, uncertainty, verification, GCI and reproducible reporting, while keeping literature support separate from run-specific evidence. A transparent CLI computes observed order, Richardson extrapolation and GCI only for a valid monotonic, approximately constant-ratio three-grid sequence.

The review layer uses the OpenAI Responses API with `gpt-5.6` and Pydantic Structured Outputs to produce a typed `EngineeringVerdict`.

The model is explicitly instructed to use only supplied evidence and exact evidence IDs. Application-side validation removes unknown references. Failed deterministic checks force a blocked result; warnings prevent an unqualified verified status. If the OpenAI API is unavailable, the product fails gracefully to a clearly labelled deterministic review instead of fabricating an AI response.

The frontend is a responsive, dependency-light JavaScript interface. The app is deployed as a hardened systemd service behind a dedicated Cloudflare Tunnel and is freely accessible without login.

### How we used Codex

Codex was the primary implementation environment for the new VES platform during Build Week. It helped us:

- inspect the existing CFD and Isaac boundaries without modifying the active Isaac bug-fix work;
- choose a separate adapter architecture instead of merging two mature projects;
- implement the typed schemas, registry, GPT-5.6 review layer, frontend and deployment;
- turn real CFD values into deterministic regression tests;
- derive and test CFD verification rules against Versteeg & Malalasekera (2007), Chapter 10;
- implement the `.vespack` integrity/privacy boundary and transparent three-grid CLI;
- identify and document the distinction between cell-count ratio and representative-grid-spacing ratio for the planned three-grid study;
- run linting, API tests, browser checks, secret scans and public deployment verification.

The repository history and Codex session record show the new Build Week implementation from architecture decision through deployment.

### Challenges

The hardest problem was not connecting an LLM. It was defining a boundary that prevents a persuasive explanation from outranking engineering evidence.

The CFD force signal is transient, decompositions use different reporting views, and discretization uncertainty is not yet closed. The robotics application was simultaneously being stabilized in another session. We therefore designed fail-closed adapters, stable IDs, explicit limitations and read-only handoffs instead of hiding those realities.

Another challenge was separating pre-existing engineering work from the new competition product. VES lives in a new repository and documents exactly what existed before Build Week and what was newly built.

### Accomplishments that we are proud of

- A working public product rather than a slide-only concept.
- One evidence contract spanning CFD and robotics.
- Deterministic checks that retain authority over the AI verdict.
- A portable, hash-validated evidence package rather than a hard-coded demo object.
- Visible method citations that never masquerade as case evidence.
- Traceable evidence citations and a reproducible SHA-256 fingerprint.
- Graceful operation when the model API is unavailable.
- A clean module template for future FEA, experiments, energy systems and test-rig modules.

### What we learned

Modularity is most useful at the evidence boundary. Solvers and simulators should keep their native workflows; the review system should consume a small, versioned export. This avoids a fragile platform rewrite and makes provenance much easier to explain.

We also learned that “the three meshes give similar answers” is not enough. A useful convergence study needs systematic representative grid spacing, observed order, Richardson extrapolation, GCI and sampling uncertainty. VES can make that missing verification visible without pretending it has already been completed.

### What's next

- complete and integrate the Laurons II three-grid convergence study;
- add rendered free-surface and project-owned CAD video evidence;
- consume the stable Isaac Skill Studio handoff and execution proof;
- add an SDK-style module manifest and third example module;
- add private, approval-gated actions while keeping the public competition build read-only.

### Build Week scope and prior work

The Laurons II CFD run and Isaac Skill Studio existed before the submission period. The new work judged for Build Week is the Verified Engineering Studio platform: shared schemas, module registry, adapters, deterministic evidence gates, GPT-5.6 structured reviews, provenance, tests, public product experience and deployment. The README and commit history document this boundary explicitly.

## Built with tags

Python, FastAPI, Pydantic, OpenAI API, GPT-5.6, OpenAI Responses API, Structured Outputs, Codex, OpenFOAM, NVIDIA Isaac Sim, JavaScript, HTML5, CSS3, Cloudflare Tunnel, GitHub, pytest, Uvicorn, Linux

## Try it out links

- Demo: https://verifiedengineeringstudio.schares-timo.de
- Short URL: https://ves.schares-timo.de
- Source: https://github.com/TimSch1912/verified-engineering-studio
- Isaac public showcase: https://isaac-sim.schares-timo.de/showcase

## Project media

- `submission/media/01-product-hero.png`
- `submission/media/02-cfd-review.png`
- `submission/media/03-module-architecture.png`

## Video demo link

Pending public YouTube upload. Do not submit the final entry until this field contains the finished video of less than three minutes.
