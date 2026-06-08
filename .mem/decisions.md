# Decisions

| id | date | decision | reason |
| --- | --- | --- | --- |
| D1 | 2026-06-08 | Product = Voice/SIP Harness, not just UserAgent/bot. | Scenarios, expectations, evidence, and timeline are the differentiator. |
| D2 | 2026-06-08 | Asterisk = backend, not conceptual core. | Asterisk accelerates PBX/media/interop but hides wire-level SIP details. |
| D3 | 2026-06-08 | MVP starts Asterisk-backed. | Delivers IVR, bot, queue, recording, trunks, and media faster. |
| D4 | 2026-06-08 | NativeSipBackend remains required. | Needed for technical softphone, raw SIP/SDP/RTP validation, lab mode, fuzzing. |
| D5 | 2026-06-08 | Core API centers on Harness, Actor, Scenario, Expect, Timeline, Verdict, Artifact. | Keeps scenarios portable across backends. |
| D6 | 2026-06-08 | Backends declare capabilities. | Prevents false claims like raw SIP assertions on Asterisk-only data. |
| D7 | 2026-06-08 | Deterministic assertions first; semantic AI assertions supplemental. | AI output is probabilistic and unsuitable as sole critical regression gate. |
| D8 | 2026-06-08 | Native protocol core should be sans-I/O. | Enables unit tests, fuzzing, fake transports, and deterministic protocol behavior. |
| D9 | 2026-06-08 | Python process stays separate from Asterisk modules. | Reduces GPL/loadable-module and maintenance risk. |
| D10 | 2026-06-08 | Use Python `>=3.14` unless project requirement changes. | Current `pyproject.toml` requires it. |
| D11 | 2026-06-08 | Public package/import name is `sipx`. | User explicitly selected `sipx`; `pyproject.toml` already matches. |
| D12 | 2026-06-08 | CLI command name is `sipx`. | Keeps command aligned with package/project identity. |
| D13 | 2026-06-08 | Technical softphone uses `NativeSipBackend`. | Final `IDEA.md` direction: Asterisk is backend/peer/resource, not softphone foundation. |
| D14 | 2026-06-08 | Technical softphone is headless engine first. | CLI/TUI/GUI should be clients of the same engine, not separate products. |
| D15 | 2026-06-08 | PJSIP/PJSUA2 is optional future backend. | Useful for robust softphone interop, but weaker for malformed/wire-level lab control. |
| D16 | 2026-06-08 | Mixed native/Asterisk scenarios are required. | Final architecture needs native actors, Asterisk actors, and remote targets in one timeline. |
| D17 | 2026-06-08 | Maintained English files in current structure replace `IDEA.md` for implementation context. | User wants no dependency on `IDEA.md` and no separate `/docs`; all implementation details must be explicit in `README.md`, `SPEC.md`, `DESIGN.md`, `TODO.md`, `.spec/*`, and `.mem/*`. |
