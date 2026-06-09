# CHANGELOG

## 1.11.0 - 2026-06-09

- Added `SipHooks` decorator-style lab hooks and removed the old `SipLabHooks` public name.
- Added `SipHandlers` decorator-style observation handlers for wire events, requests, and responses.
- Added dataclass summaries for SIP requests, responses, calls, and SDP.
- Added core SIP ID helpers and `SipUserAgent.request()` for generic requests with one-shot Digest retry and CSeq-scoped response matching.
- Added explicit `SipCapabilities` for `Accept`, `Allow`, `Allow-Events`, and `Supported` headers.
- Added compact SIP header serialization when explicitly requested.
- Added CLI dry-run message rendering with `--print-message` and `--compact-headers`.
- Added direct examples for message building and handlers.
- Bumped package version to `1.11.0`.

## 1.10.0 - 2026-06-09

- Added `SipProvisionalResponse` for configurable INVITE `1xx` UAS responses.
- Replaced the old single-provisional UAS API with `provisionals=None|()|(...)`.
- Kept default UAS answer behavior as `180 Ringing`; `provisionals=()` sends final `200 OK` directly.
- Added support for configured sequences such as `100 Trying`, `180 Ringing`, and `183 Session Progress` with optional SDP.
- Enforced RFC-shaped `100 Trying`: no To tag, no Contact, and no body.
- Added direct root SIP examples under `sipx.examples`, defaulting to the public Mizu demo with generic SIP env vars and no `argparse`.
- Made call-oriented root examples require explicit `SIPX_TARGET` and report config/call failures as structured JSON instead of tracebacks.
- Bounded call-oriented root examples by `SIPX_TIMEOUT` so provisional-only public behavior cannot hang example runs.
- Added RFC summary comments to SIP UA/UAC/UAS and request builder files.
- Bumped package version to `1.10.0`.

## 1.9.0 - 2026-06-09

- Added G.711 PCMU/PCMA encode/decode helpers without `audioop`.
- Added deterministic synthetic `silence` and `noise` PCM sources for RTP media without opening audio devices.
- Expanded RTP stats with duplicate, byte, parse/decode error, late drop, loss percent, and RFC3550-style jitter metrics.
- Added `RtpMetrics` snapshots for tx/rx packet and byte counters.
- Added `RtpJitterBuffer` with ordered playout, fixed target/max delay, concealment payloads, and underrun/overrun/duplicate/late counters.
- Moved the concrete `SipUac` and `SipUas` role classes into `sipx/uac.py` and `sipx/uas.py` while keeping `SipUserAgent` as the shared engine.
- Added high-level `SipUac` helpers for contact, register, unregister, call, hangup, and SIP INFO DTMF.
- Added high-level `SipUas` helpers for contact, answer, hangup, wait-hangup, and SIP INFO DTMF.
- Added `RtpAudioSession` with UDP RTP send/receive, PCMU/PCMA encode/decode, synthetic silence/noise send, jitter-buffer playout, and metrics snapshots.
- Wired `SipUac.call(audio="noise|silence")` and `SipUas.answer(audio="noise|silence")` to send synthetic RTP during confirmed calls.
- Added separate `rtp_bind_host` and `rtp_advertise_host` controls on high-level `SipUac`/`SipUas` media setup.
- Removed the public `sipx-softphone` workspace package and moved SIP examples plus the Mizu profile into `apps/scenarios/examples`.
- Updated CLI phone commands and no-network tests to construct `SipUac`/`SipUas` directly instead of a softphone wrapper.
- Moved the root `sipx` CLI to a SIP/RTP-only surface: `options`, `message`, `request`, `register`, `unregister`, `call`, and `listen`.
- Added CLI `call`/`listen` audio, RTP bind/advertise, jitter buffer, RTP stats, and metrics JSON flags.
- Added optional lazy PyAudio microphone input via `audio="pyaudio"` without a default native dependency.
- Added pure-Python public Mizu examples for REGISTER, OPTIONS, INVITE without SDP, INVITE with SDP/RTP, metrics, lab manipulation, and smoke checks.
- Added `FORMAT.md` with compact `SPEC.md` formatting rules.
- Recorded the architecture direction in `SPEC.md`: high-level `SipUac`/`SipUas`, SIP-only root CLI, audio modes, RTP jitter buffer, and metrics surfaces.
- Bumped package version to `1.9.0`.

## 1.8.1 - 2026-06-09

- Renamed SIP runtime public API from `Native*` names to `SipUserAgent`, `SipUac`, `SipUas`, `SipCall`, `SipHooks`, and `SipRetransmissionPolicy` without compatibility aliases.
- Renamed softphone public API to `SipSoftphone`, `SipSoftphoneAccount`, `SipSoftphoneConfig`, and `SipSoftphoneError` without compatibility aliases.
- Updated CLI/profile defaults, examples, tests, and docs to use `runtime = "sip"` and `apps/softphone/examples/sip`.
- Fixed INVITE handling so `183 Session Progress` counts as progress and the initial no-response timeout no longer fails a proceeding call.
- Added loopback regression coverage for INVITE provisional timeout behavior.
- Moved Harness, Mock, Timeline, Scenario, profile, report, recorder, and artifact surfaces into new workspace package `sipx-harness` / `sipx_harness`.
- Kept root `sipx` SIP-only: SIP/SDP/RTP/media primitives plus SIP UAC/UAS runtime.
- Moved STT/TTS speech protocols out of root `sipx.media` into `sipx-stt` / `sipx-tts` app packages.
- Moved generic redaction out of root `sipx.security` into `sipx-harness` / `sipx_harness`.
- Renamed generic public runtime contracts to `Runtime`, `CallRuntime`, `DtmfRuntime`, `RuntimeCapability`, and `MockRuntime`; removed `Backend*` API identifiers outside packaging metadata.
- Tightened text redaction so SDP `a=crypto` lines keep safe evidence shape as `a=crypto: [REDACTED]`.
- Added SIP role ABC contracts for `SipWireRuntime`, `SipUacRuntime`, and `SipUasRuntime`; `SipUserAgent` implements the SIP wire/UAC/UAS contracts.
- Kept SIP role ABC signatures explicit so concrete keyword-only UAC/UAS overrides pass `uv run ty check`.
- Configured root `pytest` to collect only core `tests/`; app tests under `apps/*/tests` are opt-in by explicit path.
- Added package-boundary regression coverage so harness symbols import from `sipx_harness`, not root `sipx`.
- Bumped package version to `1.8.1`.

## 1.8.0 - 2026-06-09

- Split the repo into a `uv` workspace with root `sipx` as the core library package.
- Moved app-specific code into `apps/llm`, `apps/softphone`, `apps/asterisk`, `apps/cli`, `apps/scenarios`, `apps/stt`, and `apps/tts` packages.
- Moved the `sipx` console command to `sipx-cli`; run it with `uv run --package sipx-cli sipx ...` from the workspace root.
- Removed LLM, softphone, Asterisk, examples, and CLI imports from the root `sipx` public API.
- Bumped package version to `1.8.0`.

## 1.7.1 - 2026-06-09

- Fixed native softphone hangup against proxies that challenge in-dialog `BYE` with `401` or `407`.
- Added one-shot Digest retry for `NativeSipBackend.hangup_call()` when credentials are available.
- Added loopback regression coverage that verifies authenticated BYE retry without persisting the password.
- Recorded SPEC B12 and invariant V38 for challenged BYE authentication.
- Bumped package version to `1.7.1`.

## 1.7.0 - 2026-06-08

- Added runnable `examples/llm/sip_flow_audit.py` for richer LLM SIP-flow analysis.
- The audit example extracts deterministic SIP signals, asks the LLM for structured JSON, and reports behavior, risk score, protocol findings, media assessment, and next actions.
- The audit example flags unredacted SIP auth headers while accepting `[REDACTED]` auth markers.
- Documented how to run the quick LLM smoke and richer SIP-flow audit examples directly or through `sipx scenario run`.
- Bumped package version to `1.7.0`.

## 1.6.1 - 2026-06-08

- Fixed `LLMChatClient.from_env()` so missing optional `SIPX_LLM_*` settings use concrete defaults instead of dataclass slot descriptors.
- Added regression coverage for minimal LLM env config used by direct example execution.
- Recorded SPEC B10 and invariant V35 for LLM env defaults.
- Bumped package version to `1.6.1`.

## 1.6.0 - 2026-06-08

- Renamed the LLM provider client to simple `LLMChatClient` with `SIPX_LLM_*` runtime environment settings.
- Added in-dialog SIP INFO DTMF support to native calls and `sipx call --dtmf`.
- Added richer native examples for register, OPTIONS, MESSAGE, raw INFO DTMF, call-with-DTMF, Mizu, and reusable CLI command arrays.
- Updated README example usage for native SIP operations and OpenAI-compatible LLM templates.
- Bumped package version to `1.6.0`.

## 1.5.0 - 2026-06-08

- Added dependency-free LLM client for opt-in scenario/template use.
- Added fake-transport LLM unit tests and a live smoke test skipped unless provider credentials are set.
- Added LLM harness, Asterisk+LLM, and native Mizu example templates that do not hardcode private secrets.
- Added template tests that import examples without requiring external credentials and scan examples for inline secret patterns.
- Fixed the existing 29-diagnostic `uv run ty check` baseline so the configured type-check gate now passes.
- Bumped package version to `1.5.0`.

## 1.4.0 - 2026-06-08

- Added SDP offer generation for native softphone outbound calls using configurable local RTP host/port and codecs.
- Added SDP answer generation for inbound native calls when the INVITE contains an audio offer.
- Added SDP answer validation on successful outbound INVITE responses before confirming a call.
- Added a lightweight local RTP UDP sink so offered RTP ports are open while the call exists.
- Added phone CLI media flags: `--media-host/--rtp-host`, `--media-port/--rtp-port`, and repeatable `--codec`.
- Added a Mizu demo profile under `examples/mizu/harness.toml` using the public demo server details.
- Recorded SPEC B7 and invariant V31 for operational softphone SDP negotiation.
- Bumped package version to `1.4.0`.

## 1.3.0 - 2026-06-08

- Added `--debug-sip` to phone and raw SIP CLI commands to print redacted SIP datagrams as they are sent and received.
- Added a strict-mode native wire event callback so debug visibility does not require lab-mode mutation hooks.
- Added no-network CLI tests that verify SIP debug output includes RX/TX packets and redacts authorization headers.
- Bumped package version to `1.3.0`.

## 1.2.1 - 2026-06-08

- Added Digest retry for `INVITE` calls and raw SIP request commands after `401` or `407` challenges when credentials are provided.
- Matched authenticated retry responses by current `CSeq` so stale challenge retransmissions are ignored.
- Added loopback Native SIP test for INVITE Digest auth retry.
- Added no-network CLI test for raw SIP request Digest auth retry.
- Recorded SPEC B6 and invariant V29 for challenged INVITE authentication.
- Bumped package version to `1.2.1`.

## 1.2.0 - 2026-06-08

- Added curl-like SIP CLI commands: `sipx options`, `sipx message`, and generic `sipx request <method> <target>`.
- Added `--from/--aor`, `--registrar`, `--remote-host`, `--remote-port`, `-H/--header`, `-d/--data`, `--body-file`, `--content-type`, `--include`, and `--no-wait` request flags.
- Added no-network CLI tests for SIP OPTIONS, MESSAGE, generic requests, missing identity, and request help.
- Bumped package version to `1.2.0`.

## 1.1.1 - 2026-06-08

- Fixed `sipx register` without profile or account flags so it fails before opening a SIP socket instead of timing out against localhost defaults.
- Made phone commands derive the default remote host and port from `--registrar` when `--remote-host` and `--remote-port` are omitted.
- Added account-flag examples to phone command help.
- Recorded SPEC B5 and invariant V27 for phone CLI configuration UX.

## 1.1.0 - 2026-06-08

- Added operational softphone CLI commands: `sipx phone register`, `unregister`, `call`, and `listen`.
- Added top-level operational aliases: `sipx register`, `unregister`, `call`, and `listen`.
- Added `sipx profile list` and `sipx profile show` for `harness.toml` profile inspection.
- Added no-network CLI tests that fake `NativeSoftphone` while validating profile and explicit account configuration.
- Added GitHub workflows for CI, Asterisk integration, draft release creation, and PyPI publishing.
- Bumped package version to `1.1.0`.

## 1.0.1 - 2026-06-08

- Added package build metadata so `uv run sipx` installs and runs the configured console script from the repo root.
- Added a regression test for the `sipx` console script build metadata.
- Recorded SPEC B4 and invariant V24 for package-manager CLI execution.

## 1.0.0 - 2026-06-08

- Added `ScenarioRecorder`, `ScenarioAction`, timeline JSONL replay loading, and CLI `sipx scenario export` for Python/YAML exports.
- Added text and HTML report generation; scenario runs now write `report.txt` and `report.html` alongside timeline and verdict artifacts.
- Added `Profile`, account/SIP/media override config, and `harness.toml` profile loading for strict and lab behavior separation.
- Added `MixedScenario` actor binding for native, Asterisk, and mock actors on one shared timeline.
- Added parser fuzz/regression tests for SIP, SDP, RTP, and RFC4733 DTMF rejection paths.
- Added `docker/asterisk` Asterisk 22 lab with ARI/PJSIP/RTP config and opt-in integration tests for ARI and Native SIP calling Asterisk as UAS.
- Documented optional future `PjsipBackend` tradeoffs.
- Marked SPEC T24-T26 and T28-T31 complete after validation.

## 0.9.5 - 2026-06-08

- Added lab-only `SipHooks` for before-send, before-SDP-body, after-receive, and retransmission interval overrides.
- Routed native SIP request, response, and retransmission sends through the lab hook pipeline while rejecting hooks in strict mode.
- Added support for lab hooks to emit malformed raw SIP bytes and to observe or drop received wire events without extending receive timeouts.
- Added `NativeSoftphoneConfig.lab_hooks` passthrough to the underlying `NativeSipBackend`.
- Added focused loopback tests for header mutation, SDP mutation, malformed send, receive observation/filtering, timer override, and softphone hook passthrough.
- Marked SPEC T23 complete after validation.

## 0.9.4 - 2026-06-08

- Added headless `NativeSoftphone` engine on top of `NativeSipBackend`.
- Added native softphone account/config models with strict/lab mode passthrough.
- Added start/stop, register/unregister, outbound call, inbound answer, and hangup methods.
- Added loopback UDP tests for softphone register/unregister, outbound call/hangup, and inbound answer.
- Marked SPEC T22 complete after validation.

## 0.9.3 - 2026-06-08

- Added an executable inbound `Stasis(sipx)` example under `sipx.examples.asterisk_stasis`.
- Added minimal Asterisk `http.conf`, `ari.conf`, and `extensions.conf` snippets with `${ARI_PASSWORD}` placeholder.
- Added inbound Stasis handling that answers, creates a bridge, creates WebSocket media, joins both channels, and optionally plays a greeting.
- Added no-Asterisk tests for config snippets, media-event filtering, ARI request sequencing, and timeline evidence.
- Marked SPEC T15 complete after validation.

## 0.9.2 - 2026-06-08

- Chose WebSocket media as the Asterisk media MVP path for the overall project.
- Added `AsteriskMediaPath`, `AsteriskMediaPortConfig`, and `AsteriskWebSocketMediaPort`.
- Added async WebSocket binary media receive/send support that converts frames to `AudioFrame` without blocking on AI work.
- Added Asterisk backend media channel and media port creation helpers with explicit errors for planned AudioSocket and ExternalMedia RTP paths.
- Added no-Asterisk tests for media path selection, injected WebSocket media frames, and local binary WebSocket frame exchange.
- Marked SPEC T11 complete after validation.

## 0.9.1 - 2026-06-08

- Added typed Asterisk ARI resource models for channels, bridges, and playbacks.
- Added Asterisk control methods for originate, answer, hangup, playback, DTMF, bridge creation, and bridge channel membership.
- Added timeline mapping for ARI requests, control results, and known channel/bridge/playback/DTMF events.
- Added no-Asterisk tests for control method request mapping and known ARI event timeline mapping.
- Marked SPEC T10 complete after validation.

## 0.9.0 - 2026-06-08

- Added `AsteriskBackend` control-plane skeleton with declared ARI capability.
- Added async ARI REST client using stdlib HTTP transport with injectable test transport.
- Added ARI WebSocket event parsing and a minimal text-frame WebSocket reader for local ARI events.
- Added timeline recording for ARI requests and ARI events without persisting credentials.
- Added no-Asterisk tests for ARI URL/auth generation, REST request behavior, error handling, timeline events, and local WebSocket event ingestion.
- Marked SPEC T9 complete after validation.

## 0.8.4 - 2026-06-08

- Added configurable transaction retransmission policy for native SIP runtime.
- Added async retransmission tasks for REGISTER, INVITE, CANCEL, BYE, and final INVITE responses until matching response/ACK arrives.
- Added retransmission timeline events and cleanup on timeout/error paths.
- Added loopback UDP test that delays REGISTER response and verifies retransmission before 200 OK.
- Marked SPEC T21 complete after validation of INVITE/ACK/BYE/CANCEL/REGISTER over real UDP plus timers.

## 0.8.3 - 2026-06-08

- Added real UDP REGISTER orchestration on `NativeSipBackend` for register and unregister flows.
- Added Digest challenge retry over UDP without storing passwords in the backend flow.
- Added REGISTER call timeline events for registered and unregistered states.
- Added loopback UDP REGISTER tests for 401 Digest retry and `Expires: 0` unregister.
- Kept full T21 open: transaction retransmission timers remain pending.

## 0.8.2 - 2026-06-08

- Added real UDP CANCEL runtime for pending INVITE attempts.
- Added pending/incoming INVITE attempt models and backend methods for `start_invite`, `receive_invite`, `cancel_invite`, and `answer_cancel`.
- Added UAS CANCEL handling with 200 OK to CANCEL, 487 Request Terminated to INVITE, and UAC ACK for the terminated INVITE.
- Added loopback UDP CANCEL test covering INVITE -> CANCEL -> 200(CANCEL) -> 487(INVITE) -> ACK.
- Kept full T21 open: REGISTER over-UDP orchestration and transaction retransmission timers remain pending.

## 0.8.1 - 2026-06-08

- Added strict UAC/UAS call runtime on `NativeSipBackend` for real UDP INVITE, provisional/final response, ACK, BYE, and BYE 200 OK flows.
- Added INVITE, ACK, and SIP response construction helpers.
- Added `NativeSipCall`, call states, and call timeline events for invite, confirmed, terminated, and failed states.
- Added loopback UDP call-flow test for INVITE -> 180/200 -> ACK -> BYE/200.
- Kept full T21 open: CANCEL runtime, REGISTER over-UDP orchestration, and transaction retransmission timers remain pending.

## 0.8.0 - 2026-06-08

- Added real async UDP SIP transport with typed RX/TX wire events, size limits, receive timeouts, and fail-closed parse errors.
- Added `NativeSipBackend` with real UDP `start`/`stop`, `send_request`, `send_response`, strict-mode raw-send rejection, lab-mode raw datagrams, and SIP timeline recording.
- Exported native SIP backend and UDP wire primitives from public package modules.
- Added loopback UDP tests for request/response exchange, timeline events, malformed datagrams, strict raw-send rejection, and receive timeout handling.
- Kept full T21 open: integrated strict UAC/UAS call flows and transaction retransmission timers remain pending.

## 0.7.3 - 2026-06-08

- Added sans-I/O REGISTER client flow with `ready`, `challenged`, `registered`, `unregistered`, and `failed` states.
- Added Digest challenge handling for 401/407 REGISTER responses and authenticated retry generation without storing passwords.
- Added unregister request creation via `Expires: 0`.
- Added tests for initial REGISTER, Digest auth retry, success/failure states, unregister, and missing challenge errors.
- Kept full T21 open: native sockets/timers, strict runtime, and integrated call flows remain pending.

## 0.7.2 - 2026-06-08

- Added UAS-side INVITE dialog creation from inbound requests.
- Added INVITE server transaction skeleton with provisional, success final, failure final, and failure ACK handling.
- Added BYE request creation helper using dialog identity and local CSeq progression.
- Added tests for UAS dialogs, INVITE server transaction state, ACK branch validation, BYE request creation, and dialog termination.
- Kept full T21 open: complete REGISTER client flow, sockets/timers, strict runtime, and integrated call flows remain pending.

## 0.7.1 - 2026-06-08

- Added non-INVITE client transaction skeleton.
- Added REGISTER request creation helper.
- Added SIP Digest challenge parsing and authorization header generation.
- Added tests for REGISTER headers, non-INVITE final response handling, and RFC Digest response generation.
- Kept full T21 open: UAS behavior, BYE flow, sockets/timers, strict runtime, and complete REGISTER client flow remain pending.

## 0.7.0 - 2026-06-08

- Added sans-I/O SIP dialog skeleton with dialog IDs, tag extraction, state transitions, and local CSeq progression.
- Added INVITE client transaction skeleton with provisional/success/failure response handling.
- Added related ACK and CANCEL request creation for INVITE transactions.
- Added tests for INVITE transaction state, ACK/CANCEL creation, dialog tags/state, and header tag parsing.
- Left full T21 open: UAS behavior, non-INVITE transactions, REGISTER, Digest auth, sockets/timers, and strict runtime are still pending.

## 0.6.0 - 2026-06-08

- Added RTP packet parse/serialize primitives for RTP v2 packets.
- Added RTP sequence statistics for received packets, gaps/loss, out-of-order packets, highest sequence, and SSRC.
- Added RFC4733 DTMF encode/decode helpers and `DtmfEvent` validation.
- Added RTP and DTMF tests.

## 0.5.0 - 2026-06-08

- Added SDP session/audio model, parser, and serializer.
- Added audio offer/answer helpers for PCMU, PCMA, and `telephone-event`.
- Added SDP direction handling for `sendrecv`, `sendonly`, `recvonly`, and `inactive`.
- Added tests for SDP parsing, serialization, offer/answer codec selection, direction inversion, and negotiation failure.

## 0.4.0 - 2026-06-08

- Added sans-I/O SIP URI, header map, message parser, and serializer primitives.
- Added typed `SipParseError` and parser bounds via `max_size`.
- Added Content-Length validation and serializer rewrite behavior.
- Added tests for SIP URI round-trip, compact header expansion, request/response parsing, Content-Length mismatch, oversized messages, and serialization.

## 0.3.0 - 2026-06-08

- Added initial media primitives and barge-in policy; speech protocol surfaces were later moved to app packages.
- Added central redaction utilities for sensitive mapping values and SIP/ARI/SDP text lines.
- Connected `ArtifactStore` JSON/text writes to the default redactor.
- Added tests for media frame validation, barge-in policy, speech event validation, redaction, and artifact redaction.
- Recorded redaction replacement bug in `SPEC.md` §B B2 and fixed it under invariant V13.

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
