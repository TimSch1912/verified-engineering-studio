# OpenAI Build Week development log

All times and dates are UTC. The Laurons II solver output and Isaac Skill Studio pre-date Build
Week; this log covers the new Verified Engineering Studio product.

## 18 July 2026

- Created a separate VES repository so the competition work is auditable and does not rewrite the
  active CFD or Isaac applications.
- Implemented a FastAPI/Pydantic module registry, deterministic discipline checks, structured
  GPT-5.6 reviews and application-side fail-closed status enforcement.
- Added a public no-login frontend, dedicated service deployment, Cloudflare Tunnel and the two
  public domains.
- Added persistent cost controls: visitor/hour and UTC/day limits, single-call concurrency,
  bounded output, timeout, disabled SDK retries and a seven-day result cache.
- Performed one controlled live GPT-5.6 review and verified deterministic fallback behavior.
- Designed the long-term dual-domain product roadmap and kept the Isaac adapter in honest
  `handoff pending` state while its separate stabilization session continues.
- Implemented `.vespack` v1 with typed manifest/provenance, exact sizes, SHA-256 index, canonical
  package identity, publication metadata and privacy/integrity rejection rules.
- Migrated the Laurons v9 case from a hard-coded JSON loader to the validated package path.
- Grounded CFD method checks in Versteeg & Malalasekera (2007), Chapter 10, with complementary ITTC
  guidance; case evidence and literature support are separate typed objects.
- Added a transparent three-grid calculator that reports observed order, extrapolation and GCI only
  for an admissible monotonic, approximately constant-ratio sequence.
- Added guided review questions, visible deterministic gates/method citations, CI and security/
  numerical regression tests.

## Explicitly pending

- stable Isaac handoff export from the independent bug-fix session;
- actual medium/coarse OpenFOAM results for the Laurons convergence study;
- refreshed screenshots and final narrated video after the current release is deployed;
- user-owned YouTube upload, Devpost final fields, feedback session ID and submission action.
