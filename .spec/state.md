# State

## Current Objective

Implement `sipx` in verified commit blocks. Block `0.7.2` adds UAS-side INVITE dialog/transaction primitives and BYE request creation.

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
- Bumped `pyproject.toml` version from `0.2.0` to `0.3.0`.
- Added `AudioFrame`, `MediaPort`, `TranscriptEvent`, STT/TTS protocols, and `BargeInPolicy`.
- Added central `Redactor` and connected `ArtifactStore` JSON/text writes to redaction.
- Added tests for media frame validation, barge-in behavior, transcript confidence validation, redaction, and artifact redaction.
- Recorded `SPEC.md` §B B2 for a redaction regex replacement bug; V13 already covered the invariant.
- Marked SPEC tasks T12 and T27 complete after verification.
- Bumped `pyproject.toml` version from `0.3.0` to `0.4.0`.
- Added `sipx.sip` package with `SipUri`, `HeaderMap`, `SipRequest`, `SipResponse`, `SipParseError`, and `parse_sip_message`.
- Added SIP parser tests for URI round-trip, compact header expansion, request/response parsing, Content-Length mismatch, oversized messages, and serializer Content-Length rewrite.
- Marked SPEC tasks T16 and T17 complete after verification.
- Bumped `pyproject.toml` version from `0.4.0` to `0.5.0`.
- Added `sipx.sdp` package with `SessionDescription`, `AudioMedia`, `SdpCodec`, `parse_sdp`, `create_audio_offer`, and `create_audio_answer`.
- Added SDP tests for audio parsing, static codecs, `telephone-event`, offer serialization, answer codec selection, direction inversion, and negotiation failure.
- Marked SPEC task T18 complete after verification.
- Bumped `pyproject.toml` version from `0.5.0` to `0.6.0`.
- Added `sipx.rtp` package with `RtpPacket`, `RtpParseError`, `RtpSequenceStats`, `RtpStatsSnapshot`, `DtmfEvent`, `encode_dtmf_event`, and `decode_dtmf_event`.
- Added RTP/DTMF tests for packet round-trip, invalid packet rejection, sequence gaps/out-of-order, and RFC4733 event encoding/decoding.
- Marked SPEC tasks T19 and T20 complete after verification.
- Bumped `pyproject.toml` version from `0.6.0` to `0.7.0`.
- Added SIP dialog skeleton with `DialogId`, `DialogState`, tag extraction, local/remote tags, local CSeq progression, and state transitions.
- Added INVITE client transaction skeleton with provisional/success/failure states and ACK/CANCEL helper request creation.
- Added SIP transaction/dialog tests.
- Kept SPEC task T21 pending because full UAC/UAS INVITE/ACK/BYE/CANCEL/REGISTER behavior is not complete.
- Bumped `pyproject.toml` version from `0.7.0` to `0.7.1`.
- Added non-INVITE client transaction skeleton.
- Added REGISTER request helper.
- Added Digest challenge parser and authorization header helper.
- Added tests for REGISTER headers, non-INVITE response handling, and RFC Digest response generation.
- Kept SPEC task T21 pending because UAS behavior, BYE flow, sockets/timers, strict runtime, and complete REGISTER client flow are not complete.
- Bumped `pyproject.toml` version from `0.7.1` to `0.7.2`.
- Added UAS-side INVITE dialog creation from inbound requests.
- Added INVITE server transaction skeleton with provisional, success final, failure final, and failure ACK handling.
- Added BYE request helper using dialog identity and local CSeq progression.
- Added tests for UAS dialogs, INVITE server transaction state, ACK branch validation, BYE request creation, and dialog termination.
- Kept SPEC task T21 pending because complete REGISTER client flow, sockets/timers, strict runtime, and integrated call flows are not complete.

## Active Decision

`sipx` should be a Voice/SIP Harness core with multiple backends. Asterisk is first backend for speed; Native SIP/RTP remains required for wire-level validation and technical softphone. The package/import name and CLI command are both `sipx`.

Maintained English files in the current structure are the source of truth. `IDEA.md` is historical source material only. A separate `/docs` tree is intentionally not used.

## Next

1. Add complete REGISTER client flow.
2. Add native SIP sockets/timers runtime shell.
3. Add richer fake media events and example mock scenario.
4. Choose first Asterisk media path.
5. Decide artifact retention policy before real recordings/transcripts.

## Risks

- Scope is large; keep MVP focused on harness core + one backend path.
- Asterisk can hide raw SIP details; do not use it for conformance claims without capture or NativeSipBackend.
- AI semantic assertions are probabilistic; do not make them sole critical-pass criterion.
- Recordings/transcripts are sensitive; design redaction/retention before real deployments.
- `ty check` is configured in docs but unavailable in the active interpreter; sync the dev environment before relying on type-check gate.
- Redaction exists but retention policy and transcript/recording-specific metadata handling are still open.
- SIP transaction/dialog skeletons exist, but T21 remains incomplete until complete REGISTER client flow, sockets/timers, strict runtime, and integrated call flows are implemented.
- RTP and DTMF primitives exist, but jitter buffer, RTCP, impairment, and media clock are not implemented yet.

## Open Questions

- First media backend: WebSocket media, AudioSocket, or ExternalMedia RTP?
- Target first user: IVR QA, contact center, or technical SIP tester?
