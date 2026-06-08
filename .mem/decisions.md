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
| D18 | 2026-06-08 | Implementation proceeds in small committed blocks with version, changelog, TODO, spec state, and memory updates every time. | User explicitly requested this pipeline so other agents follow the same flow. |
| D19 | 2026-06-08 | Initial tests avoid `pytest-asyncio` markers and use `asyncio.run`. | Active `pytest` did not load the async plugin; plain pytest compatibility keeps validation runnable. |
| D20 | 2026-06-08 | `Harness()` defaults to `MockBackend`. | Enables no-network unit tests and CLI skeleton before Asterisk or native SIP backends exist. |
| D21 | 2026-06-08 | Artifact writes use default central redaction. | Secret redaction must be automatic before logs/transcripts/recordings grow. |
| D22 | 2026-06-08 | Media layer starts with protocols and value objects, not provider adapters. | Keeps STT/TTS/LLM providers out of the media clock and avoids premature dependency choices. |
| D23 | 2026-06-08 | Native SIP starts with sans-I/O parse/serialize primitives. | Keeps protocol correctness testable before sockets, timers, transactions, or backend runtime. |
| D24 | 2026-06-08 | SDP starts with audio-only PCMU/PCMA plus `telephone-event`. | Matches MVP codec/DTMF scope without adding premature video or advanced media negotiation. |
| D25 | 2026-06-08 | RTP/DTMF starts sans-I/O before media runtime. | Packet correctness and RFC4733 event behavior should be deterministic before sockets/jitter/audio clocks. |
| D26 | 2026-06-08 | SIP transactions/dialogs start sans-I/O and partial. | T21 is broad; client INVITE and dialog state should be verified before adding UAS, REGISTER, auth, sockets, and timers. |
| D27 | 2026-06-08 | SIP Digest helper implements protocol MD5 only. | SIP Digest requires MD5 response generation; code uses `usedforsecurity=False` and does not store secrets. |
| D28 | 2026-06-08 | Continue T21 as small sans-I/O sub-blocks before native runtime. | Dialog, transaction, auth, and request correctness are easier to validate before sockets/timers and strict runtime integration. |
