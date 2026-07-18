# Verified Engineering Studio

Verified Engineering Studio (VES) turns simulation and robotics evidence into traceable
engineering reviews. A small module contract supplies typed evidence and deterministic checks;
GPT-5.6 converts that material into a structured verdict without taking authority away from the
engineering gates.

> Evidence before confidence. If a source, check, or limitation is missing, VES says so instead of
> inventing certainty.

## Competition build

This repository is the new OpenAI Build Week 2026 work product. It intentionally does not copy or
refactor the two pre-existing engineering applications.

Pre-existing work:

- Isaac Skill Studio and its generalized task/skill pipeline
- Laurons II OpenFOAM v9 calculation and project-generated visualizations

New work in this repository:

- shared `ves.evidence.v1` and `ves.review.v1` contracts
- runtime module registry and fail-closed adapter boundary
- deterministic CFD consistency gates
- read-only Isaac handoff adapter
- GPT-5.6 Responses API integration with Pydantic Structured Outputs
- review provenance, evidence hashing, public web product and module template

## Current modules

| Module | State | Public action |
|---|---|---|
| CFD Evidence Review | Ready | Review the curated Laurons II v9 evidence bundle |
| Robotics Skill Verification | Handoff pending | Inspect a read-only preview and public proof link |

The public build never starts a solver, simulator or robot. GPT-5.6 receives only a curated evidence
bundle plus deterministic check results.

## Run locally

```bash
uv venv
uv sync --extra test
uv run uvicorn ves.app:app --app-dir src --host 127.0.0.1 --port 8110
```

Open `http://127.0.0.1:8110`. API documentation is available at `/api/docs`.

The app works without an OpenAI key and clearly labels the result as a deterministic fallback. To
enable the structured GPT-5.6 review, set `OPENAI_API_KEY` in the server process environment. Never
place the real value in browser code, `.env.example`, a commit, an issue, or a screenshot.

```bash
cp .env.example .env
chmod 600 .env
./scripts/configure-openai-key.sh
```

The helper reads the key without terminal echo or shell-history exposure and updates only the
ignored `.env` file. It never prints the secret.

## Public API cost guard

The unauthenticated competition demo fails closed before making a live model request. Defaults are:

- three uncached live reviews per visitor in a rolling hour;
- twenty outbound OpenAI attempts per UTC day;
- one live request at a time, a 45-second timeout and no automatic SDK retries;
- a 1,800-token output ceiling;
- a seven-day cache for successful, identical structured verdicts.

Cache hits and deterministic fallbacks do not consume live-call quota. API failures do consume a
reservation because an upstream attempt may already have incurred usage. The daily limit can be set
to `0` as an emergency kill switch. Quotas and cached verdicts persist in SQLite; visitor addresses
are HMAC pseudonymized before storage. Questions are represented only by a one-way cache key, while
the structured model verdict is cached. OpenAI project spend alerts remain a separate
defense-in-depth control.

## Tests

```bash
uv run pytest
uv run ruff check .
node --check src/ves/static/assets/app.js
```

## Architecture

```text
question
   │
   ▼
Task Intent ──► Module Registry ──► Evidence Bundle
                                        │
                                        ├──► deterministic gates
                                        │
                                        └──► GPT-5.6 structured review
                                                   │
                                                   ▼
                                     verdict + citations + provenance
```

Every module implements four read-only methods:

```python
class EngineeringModule:
    def describe(self) -> ModuleDescriptor: ...
    def list_cases(self) -> list[CaseDescriptor]: ...
    def build_evidence(self, case_id: str) -> EvidenceBundle: ...
    def validate(self, evidence: EvidenceBundle) -> list[ValidationCheck]: ...
```

See [Adding a module](docs/ADDING_A_MODULE.md) for the extension path and
[CFD grid convergence plan](docs/GRID_CONVERGENCE_PLAN.md) for the next verification step. The
[product roadmap](docs/PRODUCT_ROADMAP.md) describes the durable dual-domain studio, portable
evidence packages and the implementation sequence beyond the competition.

## Data and media policy

Only project-generated diagrams, aggregate resistance values, solver/mesh parameters, mesh
flythroughs and project-owned CAD renderings may be committed. The Hochschule Trier LDPF page is
linked for project context; its images are not redistributed by this repository. Third-party SVA
reports, source images and protected CAD are excluded.

## License

Code is available under the MIT License. Bundled media remains copyright Timo Schares / project
contributors and is included for judging and demonstration; see [the asset register](docs/ASSET_REGISTER.md).
