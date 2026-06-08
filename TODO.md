# TODO

## Current Objective

Implement `sipx` in small verified blocks. Current code now has harness core, mock backend, scenario artifacts, CLI run/export/replay/profile/phone/raw-SIP commands, reports, profiles, mixed actor binding, media protocol primitives, central redaction, SIP parser primitives, SDP audio offer/answer, RTP/DTMF primitives, SIP dialog/transaction skeletons, REGISTER request/helper flow, Digest auth helper, UAS INVITE skeleton, BYE helper, real UDP Native SIP transport/backend, strict UAC/UAS INVITE/ACK/BYE call flow, CANCEL runtime, REGISTER over-UDP orchestration, transaction retransmission timers, native parser fuzz tests, Asterisk ARI client/events, Asterisk channel/bridge/playback/hangup/DTMF timeline mapping, WebSocket media as the Asterisk media MVP path, inbound `Stasis(sipx)` example app, Docker Asterisk lab, headless native technical softphone engine, lab-only native SIP hooks for headers, SDP, receive events, timers, and malformed bytes, GitHub CI/release workflows adapted to the new project, and fail-fast phone CLI config validation.

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

- [x] Choose first media path: WebSocket media, AudioSocket, or ExternalMedia RTP.
- [x] Create async ARI REST client.
- [x] Create ARI WebSocket event consumer.
- [x] Map ARI events to timeline events.
- [x] Implement originate, answer, hangup, playback, send DTMF.
- [x] Implement bridge creation and channel membership.
- [ ] Implement recording collection.
- [x] Add minimal `Stasis(sipx)` example config.
- [x] Add integration tests guarded by env vars and local Asterisk availability.

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
- [x] Implement lab mode hooks for controlled malformed behavior.

## Milestone 6 - Technical Softphone

- [x] Implement headless account config.
- [x] Implement profile config.
- [x] Implement register/unregister.
- [x] Implement outbound call and inbound call handlers.
- [x] Add operational CLI commands for profile inspection, register, unregister, call, and listen.
- [x] Add curl-like raw SIP CLI commands for OPTIONS, MESSAGE, and generic requests.
- [ ] Implement live SIP inspector events.
- [x] Implement strict/lab profiles.
- [x] Implement lab hooks for SIP headers, SDP, timers, and malformed behavior.
- [ ] Implement call recording and transcript collection.
- [x] Implement scenario recorder/exporter.
- [x] Implement replay from timeline/artifacts.
- [x] Add mixed scenario example with native caller, Asterisk actor, and native agent.

## Milestone 7 - Optional Backends And UI

- [x] Document `PjsipBackend` as optional future backend.
- [ ] Keep GUI/TUI out until headless engine and CLI are stable.
- [ ] Prototype technical softphone UI only as client of the engine.

## Validation Gates

- [x] `ruff format --check .`
- [x] `ruff check .`
- [ ] `python -m ty check` blocked on the system interpreter; `uv run ty check` currently reports typing diagnostics.
- [x] `pytest`
- [x] Parser fuzz/property tests once SIP/SDP/RTP parsers exist.
- [x] Asterisk integration tests only when explicit local config is present.

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
- [x] Historical note: kept `SPEC.md` T21 pending because UAS, non-INVITE, REGISTER, Digest auth, sockets/timers, and strict runtime were not complete.

## Block 0.7.1 Done

- [x] Bumped package version to `0.7.1`.
- [x] Added non-INVITE client transaction skeleton.
- [x] Added REGISTER request helper.
- [x] Added Digest challenge parser and authorization helper.
- [x] Added SIP auth/register tests.
- [x] Historical note: kept `SPEC.md` T21 pending because UAS behavior, BYE flow, sockets/timers, strict runtime, and complete REGISTER client flow were not complete.

## Block 0.7.2 Done

- [x] Bumped package version to `0.7.2`.
- [x] Added UAS-side INVITE dialog creation from inbound requests.
- [x] Added INVITE server transaction skeleton with failure ACK handling.
- [x] Added BYE request helper using dialog identity and local CSeq progression.
- [x] Added SIP transaction/dialog tests for server-side INVITE and BYE behavior.
- [x] Historical note: kept `SPEC.md` T21 pending because complete REGISTER client flow, sockets/timers, strict runtime, and integrated call flows were not complete.

## Block 0.7.3 Done

- [x] Bumped package version to `0.7.3`.
- [x] Added sans-I/O REGISTER client flow states.
- [x] Added Digest challenge processing for 401/407 and authenticated REGISTER retry generation without password storage.
- [x] Added unregister request creation via `Expires: 0`.
- [x] Added SIP auth/register tests for REGISTER flow success, failure, auth retry, unregister, and missing challenge errors.
- [x] Historical note: kept `SPEC.md` T21 pending because native sockets/timers, strict runtime, and integrated call flows were not complete.

## Block 0.8.0 Done

- [x] Bumped package version to `0.8.0`.
- [x] Added real async UDP SIP endpoint with typed wire events, parser integration, size limits, receive timeouts, and fail-closed parse-error events.
- [x] Added `NativeSipBackend` with real UDP start/stop, request/response send, lab-mode raw datagrams, strict-mode raw-send rejection, and timeline recording.
- [x] Added loopback UDP tests for request/response exchange, malformed datagrams, strict raw-send rejection, and receive timeout handling.
- [x] Historical note: kept `SPEC.md` T21 pending because integrated strict UAC/UAS call flows and transaction retransmission timers were not complete.

## Block 0.8.1 Done

- [x] Bumped package version to `0.8.1`.
- [x] Added INVITE, ACK, and generic response construction helpers.
- [x] Added strict UAC/UAS call runtime on `NativeSipBackend` for INVITE, provisional/final response, ACK, BYE, and BYE 200 OK over real UDP.
- [x] Added `NativeSipCall`, call states, and call timeline events.
- [x] Added loopback UDP test for INVITE -> 180/200 -> ACK -> BYE/200.
- [x] Historical note: kept `SPEC.md` T21 pending because CANCEL runtime, REGISTER over-UDP orchestration, and transaction retransmission timers were not complete.

## Block 0.8.2 Done

- [x] Bumped package version to `0.8.2`.
- [x] Added pending/incoming INVITE attempt models.
- [x] Added `start_invite`, `receive_invite`, `cancel_invite`, and `answer_cancel` methods on `NativeSipBackend`.
- [x] Added real UDP CANCEL flow with 200 OK to CANCEL, 487 Request Terminated to INVITE, and ACK of the terminated INVITE.
- [x] Added loopback UDP CANCEL test for INVITE -> CANCEL -> 200/487 -> ACK.
- [x] Historical note: kept `SPEC.md` T21 pending because REGISTER over-UDP orchestration and transaction retransmission timers were not complete.

## Block 0.8.3 Done

- [x] Bumped package version to `0.8.3`.
- [x] Added REGISTER and unregister orchestration over real UDP on `NativeSipBackend`.
- [x] Added Digest 401/407 retry path over UDP without backend password storage.
- [x] Added REGISTER timeline events for registered and unregistered states.
- [x] Added loopback UDP tests for Digest REGISTER and unregister `Expires: 0`.
- [x] Historical note: kept `SPEC.md` T21 pending because transaction retransmission timers were not complete.

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

## Block 0.9.1 Done

- [x] Bumped package version to `0.9.1`.
- [x] Added `AsteriskChannel`, `AsteriskBridge`, and `AsteriskPlayback` resource models.
- [x] Added ARI control methods for originate, answer, hangup, playback, DTMF, bridge creation, and bridge channel membership.
- [x] Added mapped timeline events for known ARI channel, bridge, playback, hangup, DTMF, and Stasis event types.
- [x] Added focused no-Asterisk tests for control method request mapping and known event timeline mapping.
- [x] Marked `SPEC.md` T10 complete after validation.

## Block 0.9.2 Done

- [x] Bumped package version to `0.9.2`.
- [x] Chose WebSocket media as the Asterisk media MVP path.
- [x] Added `AsteriskMediaPath`, `AsteriskMediaPortConfig`, and `AsteriskWebSocketMediaPort`.
- [x] Added async WebSocket binary media receive/send support and `AudioFrame` conversion.
- [x] Added Asterisk backend helpers for WebSocket media channel creation and media port creation.
- [x] Added explicit unsupported errors for planned AudioSocket and ExternalMedia RTP paths.
- [x] Added focused no-Asterisk tests for media path selection, injected media frames, and local binary WebSocket exchange.
- [x] Marked `SPEC.md` T11 complete after validation.

## Block 0.9.3 Done

- [x] Bumped package version to `0.9.3`.
- [x] Added `sipx.examples.asterisk_stasis` inbound `Stasis(sipx)` example.
- [x] Added minimal `http.conf`, `ari.conf`, and `extensions.conf` snippets using `${ARI_PASSWORD}` placeholder.
- [x] Added inbound handler that answers the channel, creates a bridge, creates WebSocket media, bridges both channels, and optionally plays a greeting.
- [x] Added focused no-Asterisk tests for config snippets, media-event filtering, ARI request sequencing, and timeline evidence.
- [x] Marked `SPEC.md` T15 complete after validation.

## Block 0.9.4 Done

- [x] Bumped package version to `0.9.4`.
- [x] Added `NativeSoftphone`, `NativeSoftphoneAccount`, `NativeSoftphoneConfig`, and `NativeSoftphoneError`.
- [x] Added headless start/stop, register/unregister, outbound call, inbound answer, and hangup methods over `NativeSipBackend`.
- [x] Added strict/lab mode passthrough in softphone config while keeping profile loading pending for T29.
- [x] Added focused loopback UDP tests for register/unregister, outbound call/hangup, and inbound answer.
- [x] Marked `SPEC.md` T22 complete after validation.

## Block 0.9.5 Done

- [x] Bumped package version to `0.9.5`.
- [x] Added lab-only `NativeSipLabHooks` for before-send, before-SDP-body, after-receive, and retransmission interval overrides.
- [x] Added malformed raw-byte send support through before-send lab hooks while keeping strict mode hook-free.
- [x] Added receive hook observation/filtering with timeout preservation.
- [x] Added `NativeSoftphoneConfig.lab_hooks` passthrough to `NativeSipBackend`.
- [x] Added focused loopback tests for header mutation, SDP mutation, malformed send, receive hooks, timer override, and softphone hook passthrough.
- [x] Marked `SPEC.md` T23 complete after validation.

## Block 1.0.0 Done

- [x] Bumped package version to `1.0.0`.
- [x] Added `ScenarioRecorder`, scenario export artifacts, and CLI `sipx scenario export`.
- [x] Added `sipx replay` and timeline JSONL loading.
- [x] Added automatic `report.txt` and `report.html` artifacts for scenario runs.
- [x] Added `Profile` config with strict/lab/account/SIP/media overrides loaded from `harness.toml`.
- [x] Added `MixedScenario` and `MixedActorSpec` for native/Asterisk/mock actor binding on one timeline.
- [x] Added parser fuzz/regression tests for SIP, SDP, RTP, and DTMF malformed inputs.
- [x] Added Docker Asterisk 22 lab and opt-in ARI/Native SIP integration tests.
- [x] Documented optional future `PjsipBackend` tradeoffs.
- [x] Marked `SPEC.md` T24-T26 and T28-T31 complete after validation.

## Block 1.0.1 Done

- [x] Bumped package version to `1.0.1`.
- [x] Added hatchling build metadata so `uv run sipx` installs and runs the configured console script.
- [x] Added CLI regression test for package build metadata and `sipx` console script declaration.
- [x] Added `uv.lock` for reproducible `uv` execution.
- [x] Recorded `SPEC.md` B4 and V24 for package-manager CLI execution.

## Block 1.1.0 Done

- [x] Bumped package version to `1.1.0`.
- [x] Added `sipx profile list` and `sipx profile show`.
- [x] Added `sipx phone register`, `sipx phone unregister`, `sipx phone call`, and `sipx phone listen`.
- [x] Added top-level `sipx register`, `sipx unregister`, `sipx call`, and `sipx listen` aliases.
- [x] Added no-network CLI tests with fake `NativeSoftphone` objects.
- [x] Added GitHub workflows for CI, Asterisk integration, draft release creation, and PyPI publish.
- [x] Marked `SPEC.md` T33-T34 complete after validation.

## Block 1.1.1 Done

- [x] Bumped package version to `1.1.1`.
- [x] Backpropagated `sipx register` missing-config timeout as `SPEC.md` B5 and V27.
- [x] Made phone commands fail before network access unless a profile or explicit `--aor` and `--registrar` are provided.
- [x] Made phone commands derive default remote host/port from `--registrar` when explicit remote flags are omitted.
- [x] Added account-flag examples to phone command help.
- [x] Added no-network regression tests for missing config, explicit register config, and help output.

## Block 1.2.0 Done

- [x] Bumped package version to `1.2.0`.
- [x] Added `sipx options <target>`.
- [x] Added `sipx message <target> [text]`.
- [x] Added `sipx request <method> <target>`.
- [x] Added raw SIP request flags for From identity, profile/config, remote routing, headers, body, content type, response headers, and no-wait send.
- [x] Added no-network tests for raw SIP request construction and help output.

## Blocked Or Pending

- [ ] `python -m ty check` needs the system interpreter environment synced, or validation should standardize on `uv run ty check` after fixing current typing diagnostics.
- [ ] Next Asterisk media path after WebSocket MVP remains open: AudioSocket or ExternalMedia RTP.
- [ ] License decision remains open before public distribution and Asterisk/commercial positioning.
- [ ] Silence/placeholder behavior when AI is slow remains pending.
- [ ] Advanced media/runtime behavior, recordings/transcripts, UI, and environment type-checking remain pending after 1.0.0.

## Open Questions

- Which Asterisk media path should follow WebSocket MVP: AudioSocket or ExternalMedia RTP?
- Should the first shipped product optimize for IVR testing or technical softphone?
- Which STT/TTS providers should have first adapters?
- What artifact retention/redaction policy is acceptable for real recordings?
- Is `PjsipBackend` needed before or after native SIP lab mode?
