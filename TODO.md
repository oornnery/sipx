# TODO

## Current Objective

Implement `sipx` in small verified blocks. Current code now has harness core, mock backend, scenario artifacts, minimal CLI, media protocol primitives, central redaction, SIP parser primitives, SDP audio offer/answer, RTP/DTMF primitives, SIP dialog/transaction skeletons, REGISTER request/helper flow, Digest auth helper, UAS INVITE skeleton, BYE helper, real UDP Native SIP transport/backend, strict UAC/UAS INVITE/ACK/BYE call flow, CANCEL runtime, REGISTER over-UDP orchestration, transaction retransmission timers, and an Asterisk ARI control-plane client/event skeleton.

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
- [x] Create async ARI REST client.
- [x] Create ARI WebSocket event consumer.
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
- [x] Implement transaction skeleton for INVITE and non-INVITE.
- [x] Implement dialog model with Call-ID, tags, CSeq, route set.
- [x] Implement INVITE client transaction skeleton with ACK/CANCEL helpers.
- [x] Implement non-INVITE client transaction skeleton.
- [x] Implement INVITE server transaction skeleton.
- [x] Implement REGISTER request helper.
- [x] Implement sans-I/O REGISTER client flow with Digest auth retry and unregister.
- [x] Implement Digest auth challenge/authorization helper.
- [x] Implement BYE request helper and dialog termination primitive.
- [x] Implement SDP model/parser/serializer for audio.
- [x] Implement offer/answer for PCMU, PCMA, telephone-event.
- [x] Implement RTP packet parse/serialize and sequence stats.
- [x] Implement DTMF RFC4733 events.
- [x] Implement real async UDP SIP transport and NativeSipBackend send/receive runtime.
- [x] Implement strict mode UAC/UAS basic INVITE/ACK/BYE calls over UDP.
- [x] Implement CANCEL runtime over UDP.
- [x] Implement REGISTER runtime orchestration over UDP.
- [x] Implement transaction retransmission timers for strict runtime.
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

## Block 0.6.0 Done

- [x] Bumped package version to `0.6.0`.
- [x] Added RTP packet parse/serialize primitives.
- [x] Added RTP sequence stats.
- [x] Added RFC4733 DTMF event encode/decode helpers.
- [x] Added RTP/DTMF tests.
- [x] Marked `SPEC.md` T19 and T20 complete after verification.

## Block 0.7.0 Done

- [x] Bumped package version to `0.7.0`.
- [x] Added SIP dialog ID/state model with tag extraction and local CSeq progression.
- [x] Added INVITE client transaction state handling.
- [x] Added ACK/CANCEL helper request creation for INVITE transactions.
- [x] Added SIP transaction/dialog tests.
- [ ] Kept `SPEC.md` T21 pending because UAS, non-INVITE, REGISTER, Digest auth, sockets/timers, and strict runtime are not complete.

## Block 0.7.1 Done

- [x] Bumped package version to `0.7.1`.
- [x] Added non-INVITE client transaction skeleton.
- [x] Added REGISTER request helper.
- [x] Added Digest challenge parser and authorization helper.
- [x] Added SIP auth/register tests.
- [ ] Kept `SPEC.md` T21 pending because UAS behavior, BYE flow, sockets/timers, strict runtime, and complete REGISTER client flow are not complete.

## Block 0.7.2 Done

- [x] Bumped package version to `0.7.2`.
- [x] Added UAS-side INVITE dialog creation from inbound requests.
- [x] Added INVITE server transaction skeleton with failure ACK handling.
- [x] Added BYE request helper using dialog identity and local CSeq progression.
- [x] Added SIP transaction/dialog tests for server-side INVITE and BYE behavior.
- [ ] Kept `SPEC.md` T21 pending because complete REGISTER client flow, sockets/timers, strict runtime, and integrated call flows are not complete.

## Block 0.7.3 Done

- [x] Bumped package version to `0.7.3`.
- [x] Added sans-I/O REGISTER client flow states.
- [x] Added Digest challenge processing for 401/407 and authenticated REGISTER retry generation without password storage.
- [x] Added unregister request creation via `Expires: 0`.
- [x] Added SIP auth/register tests for REGISTER flow success, failure, auth retry, unregister, and missing challenge errors.
- [ ] Kept `SPEC.md` T21 pending because native sockets/timers, strict runtime, and integrated call flows are not complete.

## Block 0.8.0 Done

- [x] Bumped package version to `0.8.0`.
- [x] Added real async UDP SIP endpoint with typed wire events, parser integration, size limits, receive timeouts, and fail-closed parse-error events.
- [x] Added `NativeSipBackend` with real UDP start/stop, request/response send, lab-mode raw datagrams, strict-mode raw-send rejection, and timeline recording.
- [x] Added loopback UDP tests for request/response exchange, malformed datagrams, strict raw-send rejection, and receive timeout handling.
- [ ] Kept `SPEC.md` T21 pending because integrated strict UAC/UAS call flows and transaction retransmission timers are not complete.

## Block 0.8.1 Done

- [x] Bumped package version to `0.8.1`.
- [x] Added INVITE, ACK, and generic response construction helpers.
- [x] Added strict UAC/UAS call runtime on `NativeSipBackend` for INVITE, provisional/final response, ACK, BYE, and BYE 200 OK over real UDP.
- [x] Added `NativeSipCall`, call states, and call timeline events.
- [x] Added loopback UDP test for INVITE -> 180/200 -> ACK -> BYE/200.
- [ ] Kept `SPEC.md` T21 pending because CANCEL runtime, REGISTER over-UDP orchestration, and transaction retransmission timers are not complete.

## Block 0.8.2 Done

- [x] Bumped package version to `0.8.2`.
- [x] Added pending/incoming INVITE attempt models.
- [x] Added `start_invite`, `receive_invite`, `cancel_invite`, and `answer_cancel` methods on `NativeSipBackend`.
- [x] Added real UDP CANCEL flow with 200 OK to CANCEL, 487 Request Terminated to INVITE, and ACK of the terminated INVITE.
- [x] Added loopback UDP CANCEL test for INVITE -> CANCEL -> 200/487 -> ACK.
- [ ] Kept `SPEC.md` T21 pending because REGISTER over-UDP orchestration and transaction retransmission timers are not complete.

## Block 0.8.3 Done

- [x] Bumped package version to `0.8.3`.
- [x] Added REGISTER and unregister orchestration over real UDP on `NativeSipBackend`.
- [x] Added Digest 401/407 retry path over UDP without backend password storage.
- [x] Added REGISTER timeline events for registered and unregistered states.
- [x] Added loopback UDP tests for Digest REGISTER and unregister `Expires: 0`.
- [ ] Kept `SPEC.md` T21 pending because transaction retransmission timers are not complete.

## Block 0.8.4 Done

- [x] Bumped package version to `0.8.4`.
- [x] Added configurable native SIP retransmission policy.
- [x] Added async retransmission timers for REGISTER, INVITE, CANCEL, BYE, and final INVITE responses.
- [x] Added retransmission timeline events and cleanup on timeout/error paths.
- [x] Added loopback UDP retransmission test with delayed REGISTER response.
- [x] Marked `SPEC.md` T21 complete after validation.

## Block 0.9.0 Done

- [x] Bumped package version to `0.9.0`.
- [x] Added `AsteriskBackend` with ARI capability declaration and timeline recording for ARI requests/events.
- [x] Added `AsteriskAriClient`, config, response, event, and typed error models.
- [x] Added async ARI REST request support with stdlib HTTP transport and injectable test transport.
- [x] Added ARI WebSocket event consumer with local text-frame reader and injectable event source.
- [x] Added focused no-Asterisk tests for URL/auth generation, REST behavior, errors, event timeline recording, and local WebSocket event ingestion.
- [x] Marked `SPEC.md` T9 complete after validation.

## Blocked Or Pending

- [ ] `ty check` needs the dev environment synced so `ty` is importable/executable.
- [ ] Asterisk media path decision remains open before Asterisk media port work.
- [ ] License decision remains open before public distribution and Asterisk/commercial positioning.
- [ ] Silence/placeholder behavior when AI is slow remains pending.
- [ ] Lab hooks, profile config, technical softphone, and advanced media/runtime behavior remain pending after T21.

## Open Questions

- Which Asterisk media path is MVP: WebSocket media, AudioSocket, or ExternalMedia RTP?
- Should the first shipped product optimize for IVR testing or technical softphone?
- Which STT/TTS providers should have first adapters?
- What artifact retention/redaction policy is acceptable for real recordings?
- Is `PjsipBackend` needed before or after native SIP lab mode?
