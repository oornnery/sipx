# CHANGELOG

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

- Added lab-only `NativeSipLabHooks` for before-send, before-SDP-body, after-receive, and retransmission interval overrides.
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

- Added media primitives: `AudioFrame`, `MediaPort`, STT/TTS protocols, `TranscriptEvent`, and barge-in policy.
- Added central redaction utilities for sensitive mapping values and SIP/ARI/SDP text lines.
- Connected `ArtifactStore` JSON/text writes to the default redactor.
- Added tests for media frame validation, barge-in policy, transcript confidence validation, redaction, and artifact redaction.
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
