# TODO

## Current Objective

Turn `IDEA.md` into an executable project plan for `sipx`: a Python Voice/SIP Harness with Asterisk-backed MVP and native SIP/RTP backend for technical softphone and protocol-level validation.

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

- [ ] Create `sipx/core/event.py` with `TimelineEvent`.
- [ ] Create `sipx/core/timeline.py` with monotonic event recording and JSONL export.
- [ ] Create `sipx/core/verdict.py` with `passed|failed|error|skipped`.
- [ ] Create `sipx/core/artifacts.py` with artifact registry and output paths.
- [ ] Create `sipx/core/actor.py` with actor identity and backend binding.
- [ ] Create `sipx/core/scenario.py` with async scenario runner skeleton.
- [ ] Create `sipx/core/expect.py` with `within`, `during`, rich failure data.
- [ ] Create `sipx/core/capabilities.py` with backend capability model.
- [ ] Add unit tests for timeline ordering, verdict generation, and unsupported expectation behavior.

## Milestone 2 - Mock Backend And CLI

- [ ] Create `MockBackend` for deterministic scenario tests without network.
- [ ] Add fake calls, fake media events, and fake SIP events.
- [ ] Add CLI entrypoint.
- [ ] Implement `sipx scenario run <file>` skeleton.
- [ ] Implement artifact output directory convention.
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

- [ ] Define `AudioFrame`.
- [ ] Define `MediaPort` protocol.
- [ ] Define STT/TTS protocols.
- [ ] Add barge-in policy model.
- [ ] Add silence/placeholder behavior when AI is slow.
- [ ] Add transcript events and media artifacts.
- [ ] Add redaction for transcripts and recordings metadata.

## Milestone 5 - NativeSipBackend MVP

- [ ] Implement SIP URI and header models.
- [ ] Implement SIP parser/serializer with bounds and typed errors.
- [ ] Implement transaction skeleton for INVITE and non-INVITE.
- [ ] Implement dialog model with Call-ID, tags, CSeq, route set.
- [ ] Implement SDP model/parser/serializer for audio.
- [ ] Implement offer/answer for PCMU, PCMA, telephone-event.
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

- [ ] `ruff format --check .`
- [ ] `ruff check .`
- [ ] `ty check`
- [ ] `pytest`
- [ ] Parser fuzz/property tests once SIP/SDP/RTP parsers exist.
- [ ] Asterisk integration tests only when explicit local config is present.

## Open Questions

- Which Asterisk media path is MVP: WebSocket media, AudioSocket, or ExternalMedia RTP?
- Should the first shipped product optimize for IVR testing or technical softphone?
- Which STT/TTS providers should have first adapters?
- What artifact retention/redaction policy is acceptable for real recordings?
- Is `PjsipBackend` needed before or after native SIP lab mode?
