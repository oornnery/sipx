# State

## Current Objective

Implement `sipx` in verified commit blocks. Block `0.2.0` delivered the initial harness core, mock backend, scenario artifact writing, and minimal CLI.

## Sources Read

- `IDEA.md`: 5270 lines; source of product architecture and roadmap.
- `AGENTS.md`: project operating rules and state-file conventions.
- `pyproject.toml`: project name `sipx`, Python `>=3.14`, dev deps `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `ty`, `taskipy`, `pre-commit`.
- `README.md`: empty at time of analysis.

## Done

- Created `SPEC.md` with §G/§C/§I/§V/§T/§B.
- Created `DESIGN.md` with architecture, entities, backends, capability model, timeline, media, security, tests, roadmap.
- Created `TODO.md` with milestones and validation gates.
- Created `.mem/hot.md`, `.mem/decisions.md`, `.mem/open-loops.md`.
- Updated `README.md` as English product orientation.
- Fixed package/import name and CLI command as `sipx`.
- Converted `SPEC.md` to English and aligned it with final `IDEA.md` direction.
- Added final `IDEA.md` details: actor-first model, headless technical softphone, strict/lab profiles, lab hooks, scenario recorder, mixed native/Asterisk scenarios, optional future PJSIP backend.
- Consolidated detailed English implementation context into current structure so implementation no longer depends on `IDEA.md` or `/docs`.
- Added `AGENTS.md` delivery pipeline: small commit blocks, version bump, changelog, TODO/state/memory updates, validation, explicit staging.
- Bumped `pyproject.toml` version from `0.1.0` to `0.2.0`.
- Created `CHANGELOG.md`.
- Created `sipx` package with core event, timeline, verdict, artifact, metrics, capabilities, expect, actor, scenario, and harness modules.
- Created `MockBackend` for deterministic no-network call scenarios.
- Added minimal CLI: `sipx scenario run <file>`.
- Added tests for timeline ordering, JSONL round-trip, capability failures, rich expectation failures, harness verdict/artifact output, and CLI scenario loading.
- Marked SPEC tasks T2-T8 and T13-T14 complete after verification.

## Active Decision

`sipx` should be a Voice/SIP Harness core with multiple backends. Asterisk is first backend for speed; Native SIP/RTP remains required for wire-level validation and technical softphone. The package/import name and CLI command are both `sipx`.

Maintained English files in the current structure are the source of truth. `IDEA.md` is historical source material only. A separate `/docs` tree is intentionally not used.

## Next

1. Add richer fake media events and example mock scenario.
2. Add redaction utilities before sensitive artifacts grow.
3. Choose first Asterisk media path.
4. Decide first shipped product focus: IVR QA, contact center, or technical SIP tester.
5. Decide artifact retention/redaction policy before real recordings/transcripts.

## Risks

- Scope is large; keep MVP focused on harness core + one backend path.
- Asterisk can hide raw SIP details; do not use it for conformance claims without capture or NativeSipBackend.
- AI semantic assertions are probabilistic; do not make them sole critical-pass criterion.
- Recordings/transcripts are sensitive; design redaction/retention before real deployments.
- `ty check` is configured in docs but unavailable in the active interpreter; sync the dev environment before relying on type-check gate.

## Open Questions

- First media backend: WebSocket media, AudioSocket, or ExternalMedia RTP?
- Target first user: IVR QA, contact center, or technical SIP tester?
