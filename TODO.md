# TODO

## Current Objective

Implement `sipx` in small verified blocks. Current code has root `sipx` package for SIP/SDP/RTP/media primitives and the httpx-like `AsyncClient` runtime (UAC verbs, UAS handlers, generic `request`, in-dialog `ack`/`bye`, Digest `AuthFlow`, event hooks, `Response.history` exposing the full provisional/auth exchange) over `sipx/protocol/*`, `sipx/transport/*`, and `sipx/rfc/*`. The legacy `SipUserAgent`/`SipUac`/`SipUas` API was removed in `3.0.0`. The `sipx` CLI is AsyncClient-based and curl-like (`options`, `message`, `request`, `register`, `unregister`). Harness concepts and generic redaction live in workspace package `apps/harness` as `sipx_harness`, with `MockRuntime` for deterministic scenarios. Asterisk, LLM, scenarios, STT, and TTS remain app packages.

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
- [x] `FORMAT.md` `SPEC.md` format rules.
- [x] `SPEC.md` goals, constraints, interfaces, invariants, tasks.
- [x] `DESIGN.md` detailed product/API/runtime/protocol/media/softphone/Asterisk/roadmap decisions.
- [x] `TODO.md` executable roadmap.
- [x] `.spec/state.md` current project state.
- [x] `.spec/handoff.md` handoff/read order.
- [x] `.mem/hot.md` compact durable facts.
- [x] `.mem/decisions.md` accepted decisions.
- [x] `.mem/open-loops.md` unresolved choices.
- [x] No separate `docs/` tree is required or desired.

## Milestone 1 - Harness Package

- [x] Create `apps/harness/src/sipx_harness/event.py` with `TimelineEvent`.
- [x] Create `apps/harness/src/sipx_harness/timeline.py` with monotonic event recording and JSONL export.
- [x] Create `apps/harness/src/sipx_harness/verdict.py` with `passed|failed|error|skipped`.
- [x] Create `apps/harness/src/sipx_harness/artifacts.py` with artifact registry and output paths.
- [x] Create `apps/harness/src/sipx_harness/actor.py` with actor identity and runtime binding.
- [x] Create `apps/harness/src/sipx_harness/scenario.py` with async scenario runner skeleton.
- [x] Create `apps/harness/src/sipx_harness/expect.py` with `within`, `during`, `not_before`, and rich failure data.
- [x] Create `apps/harness/src/sipx_harness/capabilities.py` with runtime capability model.
- [x] Add unit tests for timeline ordering, verdict generation, and unsupported expectation behavior.

## Milestone 2 - Mock Runtime And CLI

- [x] Create `MockRuntime` for deterministic scenario tests without network.
- [x] Add fake calls, fake SIP final response events, DTMF events, and hangup events.
- [x] Add CLI entrypoint.
- [x] Implement `sipx scenario run <file>` skeleton.
- [x] Implement artifact output directory convention.
- [ ] Add fake media events beyond SIP/DTMF.
- [ ] Add an example scenario using mock runtime in the current documentation structure.

## Milestone 3 - AsteriskRuntime MVP

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
- [x] Define STT/TTS protocols in `apps/stt` and `apps/tts`, not root media.
- [x] Add barge-in policy model.
- [ ] Add silence/placeholder behavior when AI is slow.
- [x] Add transcript events.
- [ ] Add media artifacts beyond timeline/verdict.
- [x] Add central redaction for harness artifact/log writes.
- [ ] Add transcript/recording-specific retention and metadata policy.

## Milestone 5 - SipUserAgent MVP

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
- [x] Implement RTP jitter/loss metrics and jitter buffer snapshots.
- [x] Implement RTP jitter buffer playout with concealment and late/drop counters.
- [x] Implement DTMF RFC4733 events.
- [x] Implement G.711 PCMU/PCMA helpers without `audioop`.
- [x] Implement synthetic `silence` and `noise` PCM sources for RTP media without audio devices.
- [x] Implement real async UDP SIP transport and `SipUserAgent` send/receive runtime.
- [x] Implement strict mode UAC/UAS basic INVITE/ACK/BYE calls over UDP.
- [x] Implement CANCEL runtime over UDP.
- [x] Implement REGISTER runtime orchestration over UDP.
- [x] Implement INVITE Digest auth retry over UDP.
- [x] Implement SDP answer validation for successful INVITE calls.
- [x] Implement transaction retransmission timers for strict runtime.
- [x] Implement lab mode hooks for controlled malformed behavior.

## Milestone 6 - Technical Softphone

- [x] Implement headless account config.
- [x] Implement profile config.
- [x] Implement register/unregister.
- [x] Implement outbound call and inbound call handlers.
- [x] Add operational CLI commands for profile inspection, register, unregister, call, and listen.
- [x] Add curl-like raw SIP CLI commands for OPTIONS, MESSAGE, and generic requests.
- [x] Add redacted SIP packet debug output for phone and raw SIP CLI commands.
- [x] Add SDP offer generation and local RTP port binding for outbound softphone calls.
- [x] Add in-dialog SIP INFO DTMF support for confirmed SIP calls.
- [x] Move high-level softphone ergonomics into `SipUac` and `SipUas`; remove `SipSoftphone*` public package/concept.
- [x] Add `RtpAudioSession` send/receive loops with G.711, synthetic audio, jitter buffer, and metrics.
- [x] Finish call-level media policy by separating RTP bind and SDP advertised addresses before marking call audio wiring complete.
- [x] Add SIP/RTP-only root CLI with curl/httpx-cli-style flags and audio/jitter/metrics options.
- [ ] Implement live SIP inspector events.
- [x] Implement strict/lab profiles.
- [x] Implement lab hooks for SIP headers, SDP, timers, and malformed behavior.
- [ ] Implement call recording and transcript collection.
- [x] Implement scenario recorder/exporter.
- [x] Implement replay from timeline/artifacts.
- [x] Add mixed scenario example with SIP caller, Asterisk actor, and SIP agent.

## Milestone 7 - Optional Runtimes And UI

- [x] Document `PjsipRuntime` as optional future runtime.
- [ ] Keep GUI/TUI out until headless engine and CLI are stable.
- [ ] Prototype technical softphone UI only as client of the engine.

## Validation Gates

- [x] `ruff format --check .`
- [x] `ruff check .`
- [x] `uv run ty check` passes; `python -m ty check` remains unavailable on the system interpreter.
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
- [x] Historical note: kept `SPEC.md` T21 pending because SIP sockets/timers, strict runtime, and integrated call flows were not complete.

## Block 0.8.0 Done

- [x] Bumped package version to `0.8.0`.
- [x] Added real async UDP SIP endpoint with typed wire events, parser integration, size limits, receive timeouts, and fail-closed parse-error events.
- [x] Added `SipUserAgent` with real UDP start/stop, request/response send, lab-mode raw datagrams, strict-mode raw-send rejection, and timeline recording.
- [x] Added loopback UDP tests for request/response exchange, malformed datagrams, strict raw-send rejection, and receive timeout handling.
- [x] Historical note: kept `SPEC.md` T21 pending because integrated strict UAC/UAS call flows and transaction retransmission timers were not complete.

## Block 0.8.1 Done

- [x] Bumped package version to `0.8.1`.
- [x] Added INVITE, ACK, and generic response construction helpers.
- [x] Added strict UAC/UAS call runtime on `SipUserAgent` for INVITE, provisional/final response, ACK, BYE, and BYE 200 OK over real UDP.
- [x] Added `SipCall`, call states, and call timeline events.
- [x] Added loopback UDP test for INVITE -> 180/200 -> ACK -> BYE/200.
- [x] Historical note: kept `SPEC.md` T21 pending because CANCEL runtime, REGISTER over-UDP orchestration, and transaction retransmission timers were not complete.

## Block 0.8.2 Done

- [x] Bumped package version to `0.8.2`.
- [x] Added pending/incoming INVITE attempt models.
- [x] Added `start_invite`, `receive_invite`, `cancel_invite`, and `answer_cancel` methods on `SipUserAgent`.
- [x] Added real UDP CANCEL flow with 200 OK to CANCEL, 487 Request Terminated to INVITE, and ACK of the terminated INVITE.
- [x] Added loopback UDP CANCEL test for INVITE -> CANCEL -> 200/487 -> ACK.
- [x] Historical note: kept `SPEC.md` T21 pending because REGISTER over-UDP orchestration and transaction retransmission timers were not complete.

## Block 0.8.3 Done

- [x] Bumped package version to `0.8.3`.
- [x] Added REGISTER and unregister orchestration over real UDP on `SipUserAgent`.
- [x] Added Digest 401/407 retry path over UDP without runtime password storage.
- [x] Added REGISTER timeline events for registered and unregistered states.
- [x] Added loopback UDP tests for Digest REGISTER and unregister `Expires: 0`.
- [x] Historical note: kept `SPEC.md` T21 pending because transaction retransmission timers were not complete.

## Block 0.8.4 Done

- [x] Bumped package version to `0.8.4`.
- [x] Added configurable SIP retransmission policy.
- [x] Added async retransmission timers for REGISTER, INVITE, CANCEL, BYE, and final INVITE responses.
- [x] Added retransmission timeline events and cleanup on timeout/error paths.
- [x] Added loopback UDP retransmission test with delayed REGISTER response.
- [x] Marked `SPEC.md` T21 complete after validation.

## Block 0.9.0 Done

- [x] Bumped package version to `0.9.0`.
- [x] Added `AsteriskRuntime` with ARI capability declaration and timeline recording for ARI requests/events.
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
- [x] Added Asterisk runtime helpers for WebSocket media channel creation and media port creation.
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
- [x] Added `SipSoftphone`, `SipSoftphoneAccount`, `SipSoftphoneConfig`, and `SipSoftphoneError`.
- [x] Added headless start/stop, register/unregister, outbound call, inbound answer, and hangup methods over `SipUserAgent`.
- [x] Added strict/lab mode passthrough in softphone config while keeping profile loading pending for T29.
- [x] Added focused loopback UDP tests for register/unregister, outbound call/hangup, and inbound answer.
- [x] Marked `SPEC.md` T22 complete after validation.

## Block 0.9.5 Done

- [x] Bumped package version to `0.9.5`.
- [x] Added lab-only `SipHooks` for before-send, before-SDP-body, after-receive, and retransmission interval overrides.
- [x] Added malformed raw-byte send support through before-send lab hooks while keeping strict mode hook-free.
- [x] Added receive hook observation/filtering with timeout preservation.
- [x] Added `SipSoftphoneConfig.lab_hooks` passthrough to `SipUserAgent`.
- [x] Added focused loopback tests for header mutation, SDP mutation, malformed send, receive hooks, timer override, and softphone hook passthrough.
- [x] Marked `SPEC.md` T23 complete after validation.

## Block 1.0.0 Done

- [x] Bumped package version to `1.0.0`.
- [x] Added `ScenarioRecorder`, scenario export artifacts, and CLI `sipx scenario export`.
- [x] Added `sipx replay` and timeline JSONL loading.
- [x] Added automatic `report.txt` and `report.html` artifacts for scenario runs.
- [x] Added `Profile` config with strict/lab/account/SIP/media overrides loaded from `harness.toml`.
- [x] Added `MixedScenario` and `MixedActorSpec` for SIP/Asterisk/mock actor binding on one timeline.
- [x] Added parser fuzz/regression tests for SIP, SDP, RTP, and DTMF malformed inputs.
- [x] Added Docker Asterisk 22 lab and opt-in ARI/SIP integration tests.
- [x] Documented optional future `PjsipRuntime` tradeoffs.
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
- [x] Added no-network CLI tests with fake `SipSoftphone` objects.
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

## Block 1.2.1 Done

- [x] Bumped package version to `1.2.1`.
- [x] Backpropagated challenged INVITE authentication as `SPEC.md` B6 and V29.
- [x] Added Digest retry for challenged INVITE calls and raw SIP request commands.
- [x] Matched authenticated retry responses by current `CSeq` to ignore stale challenge retransmissions.
- [x] Added loopback SIP test for INVITE Digest auth retry.
- [x] Added no-network CLI test for raw SIP request Digest auth retry.

## Block 1.3.0 Done

- [x] Bumped package version to `1.3.0`.
- [x] Added strict-mode SIP wire event callback for packet visibility.
- [x] Added `--debug-sip` to phone and raw SIP request CLI commands.
- [x] Printed redacted SIP TX/RX datagrams to stderr during debug runs.
- [x] Added no-network CLI tests for packet debug output and authorization redaction.

## Block 1.4.0 Done

- [x] Bumped package version to `1.4.0`.
- [x] Backpropagated authenticated `603 Declined` without SDP as `SPEC.md` B7 and V31.
- [x] Added outbound SDP offer generation for SIP softphone calls.
- [x] Added inbound SDP answer generation for INVITEs with audio offers.
- [x] Added SDP answer validation before confirming outbound calls.
- [x] Added lightweight local RTP UDP sink while calls exist.
- [x] Added phone CLI media flags for RTP host, RTP port, and codecs.
- [x] Added public Mizu demo profile example.

## Block 1.5.0 Done

- [x] Bumped package version to `1.5.0`.
- [x] Added dependency-free LLM client with injectable transport.
- [x] Added LLM unit tests using fake transport and live test skipped unless provider credentials exist.
- [x] Added LLM harness scenario example using runtime environment key only.
- [x] Added Asterisk + LLM Stasis template.
- [x] Added SIP + Mizu example helper.
- [x] Added example import and inline-secret scan tests.
- [x] Backpropagated and fixed the type-check baseline as `SPEC.md` B8 and V33.
- [x] Fixed dynamic call, mapping, URI, SDP, and media-frame typing so `uv run ty check` passes.

## Block 1.6.0 Done

- [x] Bumped package version to `1.6.0`.
- [x] Renamed LLM provider client to simple `LLMChatClient`.
- [x] Switched live LLM settings to `SIPX_LLM_API_KEY`, `SIPX_LLM_BASE_URL`, `SIPX_LLM_MODEL`, and `SIPX_LLM_TIMEOUT`.
- [x] Added SIP INFO DTMF support and `sipx call --dtmf`.
- [x] Added SIP examples for REGISTER, OPTIONS, MESSAGE, raw INFO DTMF, call-with-DTMF, and Mizu call helpers.
- [x] Updated README with concrete example usage.

## Block 1.6.1 Done

- [x] Bumped package version to `1.6.1`.
- [x] Backpropagated LLM env default failure as `SPEC.md` B10 and V35.
- [x] Fixed `LLMChatClient.from_env()` optional env defaults for direct example execution.
- [x] Added regression coverage for minimal `SIPX_LLM_API_KEY` env config.

## Block 1.7.0 Done

- [x] Bumped package version to `1.7.0`.
- [x] Added runnable `examples/llm/sip_flow_audit.py`.
- [x] Added deterministic SIP signals plus structured LLM audit JSON output.
- [x] Added deterministic auth-redaction checks for SIP-flow audit traces.
- [x] Documented direct and `sipx scenario run` commands for the quick smoke and SIP-flow audit examples.

## Block 1.7.1 Done

- [x] Bumped package version to `1.7.1`.
- [x] Backpropagated challenged BYE hangup failure as `SPEC.md` B12 and V38.
- [x] Added one-shot Digest retry for in-dialog SIP BYE when credentials are configured.
- [x] Passed softphone account credentials from `SipSoftphone.hangup()` into the user-agent hangup path.
- [x] Added loopback regression coverage for challenged BYE retry without persisting passwords.

## Block 1.8.0 Done

- [x] Bumped root package version to `1.8.0`.
- [x] Added `apps/*` as `uv` workspace packages with individual `pyproject.toml` files.
- [x] Kept root `sipx` core-only and removed LLM, softphone, Asterisk, examples, and CLI exports from root public API.
- [x] Moved LLM code/tests/examples to `apps/llm` as `sipx_llm`.
- [x] Moved softphone code/tests/examples and Mizu profile to `apps/softphone` as `sipx_softphone`.
- [x] Moved Asterisk runtime/Stasis code/tests/templates to `apps/asterisk` as `sipx_asterisk`.
- [x] Moved the console command implementation to `apps/cli` as `sipx_cli`; command is validated with `uv run --package sipx-cli sipx --help`.
- [x] Added placeholder app packages for scenarios, STT, and TTS adapters.

## Block 1.8.1 Done

- [x] Bumped root package version to `1.8.1`.
- [x] Renamed SIP runtime public classes to `SipUserAgent`, `SipUac`, `SipUas`, `SipCall`, `SipHooks`, and `SipRetransmissionPolicy` without `Native*` aliases.
- [x] Renamed softphone app public classes to `SipSoftphone`, `SipSoftphoneAccount`, `SipSoftphoneConfig`, and `SipSoftphoneError` without `Native*` aliases.
- [x] Moved softphone examples/tests to SIP naming and updated CLI/profile defaults to `runtime = "sip"`.
- [x] Fixed INVITE handling so `183 Session Progress` counts as progress and does not trigger the initial no-response timeout.
- [x] Added loopback regression coverage for a pending INVITE after provisional `183`.
- [x] Added harness runtime ABC contracts for `Runtime`, `CallRuntime`, and `DtmfRuntime` in `sipx_harness`.
- [x] Added SIP role ABC contracts for `SipWireRuntime`, `SipUacRuntime`, and `SipUasRuntime`.
- [x] Kept SIP role ABC signatures explicit so concrete keyword-only UAC/UAS overrides pass `uv run ty check`.
- [x] Configured root `pytest` to collect only core `tests/`; app tests under `apps/*/tests` are opt-in by explicit path.
- [x] Moved Harness/Mock/Timeline/Scenario surfaces to `apps/harness` as `sipx_harness` and kept root `sipx` SIP-only.
- [x] Renamed generic public `Backend*` surfaces to `Runtime*`/`user_agent` names.
- [x] Added package-boundary regression coverage for harness symbols living in `sipx_harness`, not root `sipx`.
- [x] Moved STT/TTS speech protocols out of root `sipx.media` into `sipx_stt` and `sipx_tts`.
- [x] Tightened redaction so `a=crypto` keeps a safe `a=crypto: [REDACTED]` evidence marker.
- [x] Moved generic redaction out of root `sipx.security` into `sipx_harness` and removed the root security package.

## Block 1.9.0 Done

- [x] Bumped root package version to `1.9.0`.
- [x] Added `FORMAT.md` for compact `SPEC.md` section, table, invariant, task, and backprop rules.
- [x] Added PCMU/PCMA encode/decode helpers without `audioop`.
- [x] Added synthetic `silence` and `noise` PCM sources without opening media devices.
- [x] Added RTP jitter/loss metrics, `RtpMetrics`, `RtpJitterBuffer`, and `RtpAudioSession`.
- [x] Moved concrete high-level phone ergonomics into root `SipUac` and `SipUas` modules.
- [x] Wired `SipUac.call(audio="noise|silence")` and `SipUas.answer(audio="noise|silence")` to synthetic RTP sessions.
- [x] Separated RTP bind and SDP advertised addresses for high-level UAC/UAS calls.
- [x] Ported CLI phone commands and no-network CLI tests from the removed softphone wrapper to `SipUac`/`SipUas`.
- [x] Removed `sipx-softphone` from workspace dependencies and moved SIP examples/Mizu profile to `apps/scenarios/examples`.
- [x] Removed `scenario`, `profile`, `replay`, and `phone` from the root `sipx` CLI command surface.
- [x] Added CLI `call`/`listen` flags for `--audio`, `--rtp-bind`, `--rtp-advertise`, `--jitter-buffer-ms`, `--rtp-stats`, and `--metrics-json`.
- [x] Added optional lazy PyAudio mode through `audio="pyaudio"` without a default native dependency.
- [x] Added pure-Python public Mizu examples under `apps/scenarios/examples/mizu`.
- [x] Marked `SPEC.md` T59, T65, and T66 complete after focused CLI/media/example validation.
- [x] Final validation passed: core tests, app tests, Ruff lint/format, `uv run ty check`, `git diff --check`, CLI help, and workspace package build.
- [x] Recorded CLI mock migration failure as `SPEC.md` B25.

## Block 1.10.0 Done

- [x] Bumped root package version to `1.10.0`.
- [x] Added `SipProvisionalResponse` for configurable INVITE `1xx` UAS responses.
- [x] Replaced old single-provisional UAS answer parameters with `provisionals=None|()|(...)`.
- [x] Kept default UAS answer behavior as `180 Ringing`; `provisionals=()` sends final `200 OK` directly.
- [x] Added configured `100 Trying`, `180 Ringing`, and `183 Session Progress` with optional SDP.
- [x] Enforced RFC-shaped `100 Trying`: no To tag, no Contact, no body.
- [x] Added direct root SIP examples under `sipx.examples`, defaulting to the public Mizu demo with generic SIP env vars and no `argparse`.
- [x] Made call-oriented root examples require explicit `SIPX_TARGET` and report config/call failures as structured JSON instead of tracebacks.
- [x] Bounded call-oriented root examples by `SIPX_TIMEOUT` so provisional-only public behavior cannot hang example runs.
- [x] Added RFC summary comments to SIP UA/UAC/UAS and request builder files.
- [x] Marked `SPEC.md` T67 and T68 complete after focused validation.

## Block 1.11.0 Done

- [x] Replaced `SipHooks`/`SipHandlers` decorator APIs with httpx-style `event_hooks` dict on `SipUserAgent`/`SipUac`/`SipUas`.
- [x] Events: `request`, `response`, `wire`, `sdp`, `retransmission`. Side-effect only. `sdp`/`retransmission` require lab mode.
- [x] Reduced `sipx/examples/common.py` to `account_settings()` + `print_json()` only; all examples construct UA inline.
- [x] Deleted `sipx/examples/build_request.py`.
- [x] Updated CLI `main.py` to use `event_hooks` dict with `_build_event_hooks()` helper.
- [x] Updated `apps/scenarios/examples/mizu/` to use `event_hooks` dict.
- [x] Updated tests: switched `event_hooks["response"]` to `event_hooks["wire"]` for direction-aware capture.
- [x] Bumped root package version to `1.11.0`.
- [x] Updated SPEC.md, README.md, CHANGELOG.md, .spec/*, .mem/*.
- [x] Ran Ruff lint/format, type check, whitespace, and 32 focused tests (all pass).

## Block 1.12.0 Done

- [x] Added `invalid-argument-type = "ignore"` to `[tool.ty.rules]` in pyproject.toml.
- [x] Removed `cast()` from `sipx/examples/register.py`.
- [x] Bumped root package version to `1.12.0`.
- [x] Updated CHANGELOG.md.

## Block 3.0.0 Done

- [x] Bumped package version to `3.0.0`.
- [x] Removed the legacy API entirely per user direction: deleted `sipx/legacy.py`, all legacy root exports, `SipCallSummary`/`call_summary`, `docs/old-api-snapshot/`, and `tests/test_uac_uas.py`.
- [x] Added `AsyncClient.request()` (generic method), `AsyncClient.ack()`/`AsyncClient.bye()` (in-dialog from tracked `Dialog`), and `AsyncClient.dialog()` with tests.
- [x] Rewrote the `sipx` CLI on `AsyncClient`: `options`, `message`, `request`, `register`, `unregister`; removed legacy `call`/`listen` RTP commands; rewrote CLI tests with `FakeAsyncClient`.
- [x] Deleted legacy root examples and `apps/scenarios/examples/mizu/`; trimmed `sip_cli_flow.py`; updated scenarios tests and README.
- [x] Rewrote the opt-in Asterisk SIP integration test on `AsyncClient` invite/ack/bye; harness mixed-scenario test uses `MockRuntime` for the SIP slot.
- [x] Updated `README.md`, `docs/migration.md`, `.spec/*`, and `.mem/*` to the AsyncClient-only surface.
- [x] Validation: `uv run pytest tests apps` 567 pass + 3 opt-in skips, `ruff check .` pass, `ruff format --check .` pass, `uv run ty check` pass, CLI help smoke pass.
- [ ] Pending: decide if `AsyncClient` should gain SDP/RTP orchestration to restore call/listen ergonomics; live Mizu smoke of the new examples.

## Block 2.0.0 Done

- [x] Bumped package version to `2.0.0`.
- [x] Completed the AsyncClient overhaul (`.omo/plans/sipx-overhaul.md`): `AsyncClient`, `sipx/protocol/*`, `sipx/rfc/*` (PRACK, DNS, events, presence, MESSAGE, outbound), rport, migration guide, docstrings, examples rewrite.
- [x] Moved legacy `SipUserAgent`/`SipUac`/`SipUas` into `sipx/legacy.py`; removed `sipx/ua.py`, `sipx/uac.py`, `sipx/uas.py`.
- [x] Exported `Request`, `Response`, `ClientConfig` from root `sipx`.
- [x] Converted new examples (register/invite/message/subscribe) to `SIPX_*` env vars only, honoring invariant V64 (no argparse); switched debug hooks to supported `request`/`response` events.
- [x] Fixed CLI tests to drive real `SipUserAgent.request()` via scripted no-socket fakes (Digest retry and redaction still covered).
- [x] Fixed 19 type-check errors across client/protocol/rfc/transport/tests; `uv run ty check` passes.
- [x] Added `cryptography` dev dependency so TLS connection tests run (were failing with ModuleNotFoundError).
- [x] Removed uncommitted `[tool.ruff] preview = true` experiment that broke the lint gate with 154 preview-only findings.
- [x] Validation: `pytest` 525 pass, `pytest apps` 65 pass + 3 skip, `ruff check .` pass, `ruff format --check .` pass, `uv run ty check` pass.
- [ ] Coverage gate from overhaul plan (`--cov-fail-under=90`) not reached: 82% total, 87% excluding `sipx/examples/*`; biggest gap is `sipx/legacy.py` (77%) and example scripts.

## Block 1.25.0 Done

- [x] Bumped package version to `1.25.0`.
- [x] Implemented full `TlsTransport` with `ssl.SSLContext` support, extending `TcpTransport` with TLS encryption and certificate validation per RFC 3261 §26.2 and RFC 5922.
- [x] Added `TlsConfig` dataclass with `certfile`, `keyfile`, `ca_certs`, `verify_mode`, and `check_hostname` fields.
- [x] Implemented certificate validation, hostname checking, and proper error handling with `TransportError` for TLS failures.
- [x] Added `tests/test_transport_tls.py` with 12 tests covering import, subclass verification, transport type, config dataclass, TLS connection, send/receive over TLS, close behavior, and certificate validation modes.
- [x] Replaced the previous TLS transport stub with a production-ready implementation.
- [x] Verified import, interface compliance, and TLS behavior via QA scenarios.

## Block 1.24.0 Done

- [x] Bumped package version to `1.24.0`.
- [x] Added `sipx.transport.registry.TransportRegistry` with `register()`, `create()`, and `get_supported_types()`.
- [x] Added `create_transport()` factory function using default registry with pre-registered UDP, TCP, and TLS transports.
- [x] Added `sipx.transport.tls.TlsTransport` as a minimal stub satisfying the `Transport` interface.
- [x] Added `tests/test_transport_registry.py` with 8 tests covering default registrations, creation per type, unknown type errors, custom registration, overwrite, and factory function.
- [x] Verified import, default transports, and factory creation via QA scenarios.

## Block 1.23.0 Done

- [x] Bumped package version to `1.23.0`.
- [x] Added `sipx/exceptions.py` with typed exception hierarchy.
- [x] Added `tests/test_exceptions.py` with 7 tests covering all exception types and attributes.
- [x] Verified imports, attributes, and inheritance hierarchy via QA scenarios.

## Block 1.22.0 Done

- [x] Bumped package version to `1.22.0`.
- [x] Added `sipx/models.py` with first-class `Request` and `Response` dataclasses.
- [x] Added `sipx/config.py` with `ClientConfig` dataclass.
- [x] Added `Request.build()` and `Response.from_request()` helper methods.
- [x] Added `tests/test_models.py` with 8 tests.
- [x] Added `tests/test_config.py` with 5 tests.

## Block 1.21.0 Done

- [x] Bumped root package version to `1.21.0`.
- [x] Created `sipx/types.py` with core type aliases: `SipMethod` (str), `StatusCode` (int), `HeaderName` (str), `HeaderValue` (Union[str, list[str]]), `Uri` (str).
- [x] Created new directory structure: `sipx/transport/`, `sipx/protocol/`, `sipx/rfc/`.
- [x] Added empty barrel `__init__.py` files with docstrings in new directories.
- [x] Exported new types from root `sipx.__init__` while preserving existing API.
- [x] Added `tests/test_types.py` with 3 tests verifying type alias correctness and root importability.
- [x] Added abstract `Transport` base class in `sipx.transport.base` with async `send`, `receive`, `close`, and properties `local_address`/`transport_type`.
- [x] Added `TransportConfig` dataclass with `local_host`, `local_port`, `timeout`, and `max_message_size` defaults.
- [x] Added `tests/test_transport_base.py` with mock transport covering abstractness, config defaults/overrides, send, receive, and close.
- [x] Verified import, abstractness, and dataclass behavior via QA scenarios.

## Block 1.20.0 Done

- [x] Bumped root package version to `1.20.0`.
- [x] Created `.spec/rfc-compliance.md` with compliance matrix for all 10 targeted RFCs.
- [x] Covered RFC 3261 (SIP core), RFC 3262 (PRACK), RFC 3263 (DNS), RFC 3264 (SDP offer/answer), RFC 3265 (event notification), RFC 3581 (rport), RFC 3856 (presence), RFC 3858 (PIDF), RFC 3428 (MESSAGE), and RFC 5626 (outbound).
- [x] Each RFC has a table with Requirement, MUST/SHOULD/MAY, Status, and Test Evidence columns.
- [x] All requirements start with "Planned" status for future task tracking.
- [x] Included RFC citations with links to official documents.
- [x] Verified file structure with QA scenarios.

## Block 1.19.0 Done

- [x] Added `RtpWireDirection`, `RtpWireEvent` dataclass for RTP packet tx/rx visibility.
- [x] Added `event_hooks["rtp"]` support to `RtpAudioSessionConfig`; hooks fire on send/receive.
- [x] Added `debug_wire_rtp()` to `sipx.examples.common` with bordered SSRC/seq/ts/pt/payload format.
- [x] Wired `event_hooks["rtp"]` through `SipUac` and `SipUas` into `RtpAudioSession`.
- [x] Exported `RtpWireDirection`/`RtpWireEvent` from `sipx.rtp` and root `sipx.__init__`.
- [x] Enabled `debug_wire_rtp` in `metrics.py` and `invite_with_sdp.py` examples.
- [x] All 90 core tests pass; ruff/type-check clean.
- [x] Bumped root package version to `1.19.0`.

## Blocked Or Pending

- [ ] `python -m ty check` still needs the system interpreter environment synced; configured validation now uses passing `uv run ty check`.
- [ ] Next Asterisk media path after WebSocket MVP remains open: AudioSocket or ExternalMedia RTP.
- [ ] License decision remains open before public distribution and Asterisk/commercial positioning.
- [ ] Silence/placeholder behavior when AI is slow remains pending.
- [ ] Live SIP inspector events remain pending after 1.11.0.
- [ ] Advanced media/runtime behavior, recordings/transcripts, UI, and system-interpreter tooling remain pending after 1.11.0.

## Open Questions

- Which Asterisk media path should follow WebSocket MVP: AudioSocket or ExternalMedia RTP?
- Should the first shipped product optimize for IVR testing or technical softphone?
- Which STT/TTS providers should have first adapters?
- What artifact retention/redaction policy is acceptable for real recordings?
- Is `PjsipRuntime` needed before or after SIP lab mode?
