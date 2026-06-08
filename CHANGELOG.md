# CHANGELOG

## 0.2.0 - 2026-06-08

- Added the initial `sipx` Python package with public exports for `Harness`, `Actor`, `Scenario`, `expect`, `Timeline`, `Verdict`, `Artifact`, metrics, and backend capabilities.
- Added `MockBackend` for network-free scenarios with mock call start, SIP final response, DTMF, and hangup timeline events.
- Added scenario execution with minimum artifacts: `timeline.jsonl` and `verdict.json`.
- Added minimal CLI entrypoint: `sipx scenario run <file>`.
- Added unit tests for timeline ordering, artifact/verdict generation, unsupported capabilities, expectation failures, harness execution, and CLI scenario loading.
- Updated `AGENTS.md` with the preferred delivery pipeline: small commit blocks, version bump, changelog, TODO/state/memory updates, validation, explicit staging.

## 0.1.0 - 2026-06-08

- Added initial project planning/spec state for `sipx`.
- Defined product direction as a Python programmable Voice/SIP Harness with Asterisk and Native SIP backends.
