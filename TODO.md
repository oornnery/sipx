# TODO

## Current Objective

Implement `sipx` in small verified blocks. Current code now has harness core, mock backend, scenario artifacts, minimal CLI, media protocol primitives, central redaction, SIP parser primitives, and SDP audio offer/answer.

## Milestone 0 - Project Grounding

- [x] Create `SPEC.md` from `IDEA.md`.
- [x] Create `DESIGN.md` from `IDEA.md`.
- [x] Create project state files under `.spec/`.
- [x] Create memory files under `.mem/`.
- [x] Update `README.md` with product identity and quick start.
- [x] Decide package import name: `sipx`.
- [x] Decide CLI command name: `sipx`.
- [x] Consolidate detailed English implementation context into current structure so implementation no longer depends on `IDEA.md` or `/docs`.
- [ ] Decide license before Asterisk/commercial positioning.

## Documentation Source Of Truth

- [x] `README.md` product orientation and source-of-truth map.
- [x] `SPEC.md` goals, constraints, interfaces, invariants, tasks.
- [x] `DESIGN.md` detailed product/API/backend/protocol/media/softphone/Asterisk/roadmap decisions.
- [x] `TODO.md` executable roadmap.
- [x] `.spec/state.md` current project state.
- [x] `.spec/handoff.md` handoff/read order.
- [x] `.mem/hot.md` compact durable facts.
- [x] `.mem/decisions.md` accepted decisions.
- [x] `.mem/open-loops.md` unresolved choices.
- [x] No separate `docs/` tree is required or desired.

## Milestone 1 - Harness Core

- [x] Create `sipx/core/event.py` with `TimelineEvent`.
- [x] Create `sipx/core/timeline.py` with monotonic event recording and JSONL export.
- [x] Create `sipx/core/verdict.py` with `passed|failed|error|skipped`.
- [x] Create `sipx/core/artifacts.py` with artifact registry and output paths.
- [x] Create `sipx/core/actor.py` with actor identity and backend binding.
- [x] Create `sipx/core/scenario.py` with async scenario runner skeleton.
- [x] Create `sipx/core/expect.py` with `within`, `during`, `not_before`, and rich failure data.
- [x] Create `sipx/core/capabilities.py` with backend capability model.
- [x] Add unit tests for timeline ordering, verdict generation, and unsupported expectation behavior.

## Milestone 2 - Mock Backend And CLI

- [x] Create `MockBackend` for deterministic scenario tests without network.
- [x] Add fake calls, fake SIP final response events, DTMF events, and hangup events.
- [x] Add CLI entrypoint.
- [x] Implement `sipx scenario run <file>` skeleton.
- [x] Implement artifact output directory convention.
- [ ] Add fake media events beyond SIP/DTMF.
- [ ] Add an example scenario using mock backend in the current documentation structure.

## Milestone 3 - AsteriskBackend MVP

- [ ] Choose first media path: WebSocket media, AudioSocket, or ExternalMedia RTP.
- [ ] Create async ARI REST client.
- [ ] Create ARI WebSocket event consumer.
- [ ] Map ARI events to timeline events.
- [ ] Implement originate, answer, hangup, playback, send DTMF.
- [ ] Implement bridge creation and channel membership.
- [ ] Implement recording collection.
- [ ] Add minimal `Stasis(sipx)` example config.
- [ ] Add integration tests guarded by env vars and local Asterisk availability.

## Milestone 4 - Media And AI Runtime

- [x] Define `AudioFrame`.
- [x] Define `MediaPort` protocol.
- [x] Define STT/TTS protocols.
- [x] Add barge-in policy model.
- [ ] Add silence/placeholder behavior when AI is slow.
- [x] Add transcript events.
- [ ] Add media artifacts beyond timeline/verdict.
- [x] Add central redaction for artifact/log writes.
- [ ] Add transcript/recording-specific retention and metadata policy.

## Milestone 5 - NativeSipBackend MVP

- [x] Implement SIP URI and header models.
- [x] Implement SIP parser/serializer with bounds and typed errors.
- [ ] Implement transaction skeleton for INVITE and non-INVITE.
- [ ] Implement dialog model with Call-ID, tags, CSeq, route set.
- [x] Implement SDP model/parser/serializer for audio.
- [x] Implement offer/answer for PCMU, PCMA, telephone-event.
- [ ] Implement RTP packet parse/serialize and sequence stats.
- [ ] Implement DTMF RFC4733 events.
- [ ] Implement strict mode UAC/UAS basic calls.
- [ ] Implement lab mode hooks for controlled malformed behavior.

## Milestone 6 - Technical Softphone

- [ ] Implement account/profile config.
- [ ] Implement register/unregister.
- [ ] Implement outbound call and inbound call handlers.
- [ ] Implement live SIP inspector events.
- [ ] Implement strict/lab profiles.
- [ ] Implement lab hooks for SIP headers, SDP, timers, and malformed behavior.
- [ ] Implement call recording and transcript collection.
- [ ] Implement scenario recorder/exporter.
- [ ] Implement replay from timeline/artifacts.
- [ ] Add mixed scenario example with native caller, Asterisk actor, and native agent.

## Milestone 7 - Optional Backends And UI

- [ ] Document `PjsipBackend` as optional future backend.
- [ ] Keep GUI/TUI out until headless engine and CLI are stable.
- [ ] Prototype technical softphone UI only as client of the engine.

## Validation Gates

- [x] `ruff format --check .`
- [x] `ruff check .`
- [ ] `ty check` blocked: `ty` is not installed in the active Python environment.
- [x] `pytest`
- [ ] Parser fuzz/property tests once SIP/SDP/RTP parsers exist.
- [ ] Asterisk integration tests only when explicit local config is present.

## Block 0.2.0 Done

- [x] Bumped package version to `0.2.0`.
- [x] Created `CHANGELOG.md`.
- [x] Updated `AGENTS.md` with the preferred block delivery pipeline.
- [x] Added `sipx` package exports and CLI script metadata.
- [x] Added tests for core harness behavior and minimal CLI.

## Block 0.3.0 Done

- [x] Bumped package version to `0.3.0`.
- [x] Added media primitives and protocol interfaces.
- [x] Added barge-in policy.
- [x] Added central redaction utilities and connected them to `ArtifactStore`.
- [x] Added media and redaction tests.
- [x] Marked `SPEC.md` T12 and T27 complete after verification.

## Block 0.4.0 Done

- [x] Bumped package version to `0.4.0`.
- [x] Added sans-I/O SIP URI, HeaderMap, parser, serializer, and typed parse errors.
- [x] Added Content-Length and max-size validation.
- [x] Added SIP parser/serializer tests.
- [x] Marked `SPEC.md` T16 and T17 complete after verification.

## Block 0.5.0 Done

- [x] Bumped package version to `0.5.0`.
- [x] Added SDP session/audio model, parser, and serializer.
- [x] Added audio offer/answer helpers for PCMU, PCMA, and `telephone-event`.
- [x] Added SDP tests.
- [x] Marked `SPEC.md` T18 complete after verification.

## Blocked Or Pending

- [ ] `ty check` needs the dev environment synced so `ty` is importable/executable.
- [ ] Asterisk media path decision remains open before AsteriskBackend MVP.
- [ ] License decision remains open before public distribution and Asterisk/commercial positioning.
- [ ] Silence/placeholder behavior when AI is slow remains pending.
- [ ] SIP transaction/dialog and RTP/DTMF work remains pending after SIP/SDP primitives.

## Open Questions

- Which Asterisk media path is MVP: WebSocket media, AudioSocket, or ExternalMedia RTP?
- Should the first shipped product optimize for IVR testing or technical softphone?
- Which STT/TTS providers should have first adapters?
- What artifact retention/redaction policy is acceptable for real recordings?
- Is `PjsipBackend` needed before or after native SIP lab mode?
