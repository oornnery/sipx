# State

## Current Objective

Implement `sipx` in verified commit blocks. Block `1.8.0` splits the repo into a core-only root `sipx` package plus app-specific `uv` workspace packages under `apps/*`.

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
- Bumped `pyproject.toml` version from `0.7.2` to `0.7.3`.
- Added sans-I/O REGISTER client flow states.
- Added Digest challenge handling for 401/407 REGISTER responses and authenticated retry generation without storing passwords.
- Added unregister request creation via `Expires: 0`.
- Added tests for initial REGISTER, Digest auth retry, success/failure states, unregister, and missing challenge errors.
- Kept SPEC task T21 pending because native sockets/timers, strict runtime, and integrated call flows are not complete.
- Bumped `pyproject.toml` version from `0.7.3` to `0.8.0`.
- Added real async UDP SIP endpoint with typed wire events, parser integration, size limits, receive timeouts, and fail-closed parse-error events.
- Added `NativeSipBackend` with real UDP start/stop, request/response send, lab-mode raw datagrams, strict-mode raw-send rejection, and timeline recording.
- Added loopback UDP tests for request/response exchange, malformed datagrams, strict raw-send rejection, and receive timeout handling.
- Kept SPEC task T21 pending because integrated strict UAC/UAS call flows and transaction retransmission timers are not complete.
- Bumped `pyproject.toml` version from `0.8.0` to `0.8.1`.
- Added INVITE, ACK, and generic response construction helpers.
- Added strict UAC/UAS call runtime on `NativeSipBackend` for INVITE, provisional/final response, ACK, BYE, and BYE 200 OK over real UDP.
- Added `NativeSipCall`, call states, and call timeline events.
- Added loopback UDP test for INVITE -> 180/200 -> ACK -> BYE/200.
- Kept SPEC task T21 pending because CANCEL runtime, REGISTER over-UDP orchestration, and transaction retransmission timers are not complete.
- Bumped `pyproject.toml` version from `0.8.1` to `0.8.2`.
- Added pending/incoming INVITE attempt models.
- Added `start_invite`, `receive_invite`, `cancel_invite`, and `answer_cancel` methods on `NativeSipBackend`.
- Added real UDP CANCEL flow with 200 OK to CANCEL, 487 Request Terminated to INVITE, and ACK of the terminated INVITE.
- Added loopback UDP CANCEL test for INVITE -> CANCEL -> 200/487 -> ACK.
- Kept SPEC task T21 pending because REGISTER over-UDP orchestration and transaction retransmission timers are not complete.
- Bumped `pyproject.toml` version from `0.8.2` to `0.8.3`.
- Added REGISTER and unregister orchestration over real UDP on `NativeSipBackend`.
- Added Digest 401/407 retry path over UDP without backend password storage.
- Added REGISTER timeline events for registered and unregistered states.
- Added loopback UDP tests for Digest REGISTER and unregister `Expires: 0`.
- Kept SPEC task T21 pending because transaction retransmission timers are not complete.
- Bumped `pyproject.toml` version from `0.8.3` to `0.8.4`.
- Added configurable native SIP retransmission policy.
- Added async retransmission timers for REGISTER, INVITE, CANCEL, BYE, and final INVITE responses until matching response/ACK arrives.
- Added retransmission timeline events and cleanup on timeout/error paths.
- Added loopback UDP test with delayed REGISTER response to verify retransmission before 200 OK.
- Marked SPEC task T21 complete after validation.
- Bumped `pyproject.toml` version from `0.8.4` to `0.9.0`.
- Added `AsteriskBackend` control-plane skeleton with `ASTERISK_ARI`, `CALL_CONTROL`, and `TIMELINE` capabilities.
- Added `AsteriskAriConfig`, `AsteriskAriClient`, `AsteriskAriEvent`, `AsteriskAriHttpResponse`, and `AsteriskAriError`.
- Added async ARI REST request support using stdlib HTTP transport with injectable test transport.
- Added ARI WebSocket event consumption with injectable event source and a local minimal text-frame reader.
- Added timeline events for ARI requests and ARI events without recording credentials.
- Added no-Asterisk tests for ARI URL/auth generation, REST request/error behavior, event timeline recording, and local WebSocket event ingestion.
- Marked SPEC task T9 complete after validation.
- Bumped `pyproject.toml` version from `0.9.0` to `0.9.1`.
- Added `AsteriskChannel`, `AsteriskBridge`, and `AsteriskPlayback` typed resource models.
- Added `AsteriskBackend` methods for originate, answer, hangup, playback, DTMF, bridge creation, and bridge channel membership.
- Added known ARI event mapping for Stasis, channel state/destroyed, DTMF, bridge membership, and playback lifecycle events.
- Added timeline event recording for Asterisk control method results and known ARI events.
- Added no-Asterisk tests for control method request mapping and known ARI event timeline mapping.
- Marked SPEC task T10 complete after validation.
- Bumped `pyproject.toml` version from `0.9.1` to `0.9.2`.
- Chose WebSocket media as the Asterisk media MVP path for the overall project.
- Added `AsteriskMediaPath`, `AsteriskMediaPortConfig`, and `AsteriskWebSocketMediaPort`.
- Added async WebSocket binary media receive/send support and `AudioFrame` conversion without synchronous AI calls.
- Added Asterisk backend helpers for WebSocket media channel creation and media port creation.
- Added explicit unsupported errors for planned AudioSocket and ExternalMedia RTP paths.
- Added no-Asterisk tests for media path selection, injected media frames, and local binary WebSocket exchange.
- Marked SPEC task T11 complete after validation.
- Bumped `pyproject.toml` version from `0.9.2` to `0.9.3`.
- Added `sipx.examples.asterisk_stasis` inbound `Stasis(sipx)` example.
- Added minimal Asterisk `http.conf`, `ari.conf`, and `extensions.conf` snippets with `${ARI_PASSWORD}` placeholder.
- Added inbound handler that filters media-channel `StasisStart`, answers inbound channels, creates bridges, creates WebSocket media, joins both channels, and optionally plays a greeting.
- Added no-Asterisk tests for config snippets, event filtering, ARI request sequencing, and timeline evidence.
- Marked SPEC task T15 complete after validation.
- Bumped `pyproject.toml` version from `0.9.3` to `0.9.4`.
- Added `sipx.softphone.NativeSoftphone` headless technical softphone engine on `NativeSipBackend`.
- Added `NativeSoftphoneAccount`, `NativeSoftphoneConfig`, and `NativeSoftphoneError`.
- Added start/stop, register/unregister, outbound call, inbound answer, and hangup methods.
- Added strict/lab mode passthrough in softphone config while leaving profile loading for T29.
- Added loopback UDP tests for softphone register/unregister, outbound call/hangup, and inbound answer.
- Marked SPEC task T22 complete after validation.
- Bumped `pyproject.toml` version from `0.9.4` to `0.9.5`.
- Added `NativeSipLabHooks` with before-send, before-SDP-body, after-receive, and retransmission interval hooks.
- Routed native SIP request/response/retransmission sends through lab hooks while rejecting hooks in strict mode.
- Added lab hook support for malformed raw bytes and receive event observation/filtering with timeout preservation.
- Added `NativeSoftphoneConfig.lab_hooks` passthrough to `NativeSipBackend`.
- Added focused loopback tests for header mutation, SDP mutation, malformed send, receive hooks, timer override, and softphone hook passthrough.
- Marked SPEC task T23 complete after validation.
- Bumped `pyproject.toml` version from `0.9.5` to `1.0.0`.
- Added `ScenarioRecorder`, `ScenarioAction`, timeline JSONL loading, Python/YAML exports, and CLI `sipx scenario export`.
- Added CLI `sipx replay` and text/HTML report generation; scenario runs now write `timeline.jsonl`, `verdict.json`, `report.txt`, and `report.html`.
- Added `Profile`, `ProfileAccount`, `SipOverrides`, `MediaOverrides`, and `load_profiles()` for `harness.toml` strict/lab/account/media overrides.
- Added `MixedScenario` and `MixedActorSpec` to bind native, Asterisk, and mock actors onto one shared timeline.
- Added parser fuzz/regression tests for malformed SIP, SDP, RTP, and DTMF inputs.
- Added `docker/asterisk` Asterisk 22 lab with ARI/PJSIP/RTP config and opt-in ARI plus Native SIP integration tests.
- Documented optional future `PjsipBackend` tradeoffs.
- Marked SPEC tasks T24-T26 and T28-T31 complete after validation.
- Bumped `pyproject.toml` version from `1.0.0` to `1.0.1`.
- Added hatchling build metadata so `uv run sipx` installs and runs the configured console script.
- Added CLI regression test for `[project.scripts].sipx` and `[build-system]` metadata.
- Added `uv.lock` generated by `uv run` for reproducible uv execution.
- Recorded SPEC B4 and invariant V24 for package-manager CLI execution.
- Bumped `pyproject.toml` version from `1.0.1` to `1.1.0`.
- Added `sipx profile list` and `sipx profile show`.
- Added `sipx phone register`, `sipx phone unregister`, `sipx phone call`, and `sipx phone listen`.
- Added top-level aliases `sipx register`, `sipx unregister`, `sipx call`, and `sipx listen`.
- Added no-network CLI tests that fake `NativeSoftphone` while validating profile and explicit account configuration.
- Added `.github/workflows/ci.yml`, `asterisk.yml`, `create-release.yml`, and `release.yml` using Python 3.14, current project metadata, uv, ruff, pytest, package build, Docker Asterisk integration, and PyPI trusted publishing.
- Marked SPEC tasks T33-T34 complete after validation.
- Committed and force-pushed the new project to `origin/master` at `8457a73`; old remote branches `dev` and `copilot/modularize-sipx-modules` were deleted.
- Deleted old remote Git tags `v0.0.4` through `v0.0.7` and old GitHub release records `v0.0.4` through `v0.0.7`.
- Bumped `pyproject.toml` version from `1.1.0` to `1.1.1`.
- Recorded SPEC B5 and V27 after `sipx register` without profile/flags timed out against localhost defaults.
- Added fail-fast phone CLI validation: commands require a profile or explicit `--aor` and `--registrar` before opening network sockets.
- Phone commands now derive default remote host and port from `--registrar` when `--remote-host` and `--remote-port` are omitted.
- Added phone CLI help examples and no-network regression tests for missing config, explicit register config, and help output.
- Bumped `pyproject.toml` version from `1.1.1` to `1.2.0`.
- Added `sipx options <target>`, `sipx message <target> [text]`, and `sipx request <method> <target>`.
- Added raw SIP request flags: `--from/--aor`, `--registrar`, `--remote-host`, `--remote-port`, `-H/--header`, `-d/--data`, `--body-file`, `--content-type`, `--include`, and `--no-wait`.
- Raw SIP request commands build minimal Via/From/To/Call-ID/CSeq/Contact/Max-Forwards headers, send via `NativeSipBackend`, and match responses by Call-ID/CSeq.
- Added no-network tests for OPTIONS, MESSAGE, generic INFO request, missing From identity, and request help output.
- Recorded SPEC B6 and V29 after a real proxy returned `401 Unauthorized` to INVITE and the call path did not retry Digest.
- Added Digest retry for INVITE calls and raw SIP request commands after `401` or `407` when credentials exist.
- Added loopback Native SIP test for INVITE Digest retry and no-network CLI test for raw request Digest retry.
- Bumped `pyproject.toml` version from `1.2.0` to `1.2.1`.
- Retested the real proxy call without persisting secrets; the challenge was retried and the proxy returned `603 Declined` instead of the previous `401 Unauthorized`.
- Added current-`CSeq` response matching for authenticated retries so stale pre-auth challenge retransmissions are ignored.
- Bumped `pyproject.toml` version from `1.2.1` to `1.3.0`.
- Added a strict-mode `NativeSipBackend` wire event callback for packet visibility without lab-mode mutation hooks.
- Added `--debug-sip` to phone and raw SIP request CLI commands; debug output prints redacted SIP datagrams to stderr.
- Added no-network CLI tests that verify debug output includes TX/RX packets and redacts authorization headers.
- Recorded SPEC B7 and V31 after an authenticated real proxy INVITE reached `603 Declined` while the softphone INVITE had no SDP offer or open RTP port.
- Bumped `pyproject.toml` version from `1.3.0` to `1.4.0`.
- Added outbound SDP audio offers for native softphone calls using configurable media host, media port, codecs, and telephone-event support.
- Added inbound SDP answer generation for INVITEs with audio offers.
- Added outbound `2xx` SDP answer validation before call confirmation.
- Added a lightweight local RTP UDP sink so the advertised RTP port is open while a call exists.
- Added phone CLI flags `--media-host/--rtp-host`, `--media-port/--rtp-port`, and repeatable `--codec`.
- Added public Mizu demo profile at `examples/mizu/harness.toml`; private proxy data remains excluded from repo files.
- Bumped `pyproject.toml` version from `1.4.0` to `1.5.0`.
- Added dependency-free LLM client with injectable stdlib HTTP transport.
- Added fake-transport LLM tests and a live smoke test skipped unless runtime provider credentials are set.
- Added LLM harness, Asterisk+LLM, and native Mizu example templates.
- Added tests that import templates without external secrets and scan examples for inline secret patterns.
- Backpropagated the type-check baseline as `SPEC.md` B8 and V33.
- Fixed dynamic call, mapping, URI, SDP direction, and media-frame typing so `uv run ty check` passes.
- Bumped `pyproject.toml` version from `1.5.0` to `1.6.0`.
- Renamed the LLM client to `LLMChatClient` and switched live env settings to `SIPX_LLM_*`.
- Added in-dialog SIP INFO DTMF support through `NativeSoftphone.send_dtmf()` and `sipx call --dtmf`.
- Added native examples for REGISTER, OPTIONS, MESSAGE, raw INFO DTMF, call-with-DTMF, Mizu call helpers, and reusable CLI command arrays.
- Updated README with concrete example commands and Python template usage.
- Recorded `SPEC.md` B9 after focused validation caught incomplete DTMF backend wiring; V34 already covered the behavior.
- Bumped `pyproject.toml` version from `1.6.0` to `1.6.1`.
- Recorded `SPEC.md` B10 and V35 after direct LLM example execution failed when optional `SIPX_LLM_TIMEOUT` was missing.
- Fixed `LLMChatClient.from_env()` to use concrete defaults for optional env settings.
- Bumped `pyproject.toml` version from `1.6.1` to `1.7.0`.
- Added `examples/llm/sip_flow_audit.py` as a richer runnable LLM SIP-flow audit example with deterministic signals and structured JSON output.
- Recorded `SPEC.md` B11 and V37 after focused validation caught redacted auth being treated as unredacted in the SIP-flow audit.
- Bumped `pyproject.toml` version from `1.7.0` to `1.7.1`.
- Recorded `SPEC.md` B12 and V38 after a real confirmed call failed hangup when the proxy challenged BYE with `401 Unauthorized`.
- Added one-shot Digest retry for in-dialog BYE and passed softphone account credentials into hangup.
- Verified the real proxy flow reached authenticated BYE `200 OK`; no real account, proxy, number, or password values are persisted in repo files.
- Bumped `pyproject.toml` version from `1.7.1` to `1.8.0`.
- Added `apps/*` workspace packages for CLI, softphone, Asterisk, LLM, scenarios, STT, and TTS.
- Moved app-specific LLM, softphone, Asterisk, examples, tests, and CLI code out of root `sipx`; root public API now exports core/protocol/native SIP surfaces only.
- Marked `SPEC.md` T47 complete after workspace validation.

## Active Decision

`sipx` should be a Voice/SIP Harness core with multiple backends. Asterisk is first backend for speed; Native SIP/RTP remains required for wire-level validation and technical softphone. The package/import name and CLI command are both `sipx`.

Maintained English files in the current structure are the source of truth. `IDEA.md` is historical source material only. A separate `/docs` tree is intentionally not used.

## Next

1. Decide license before public distribution and Asterisk/commercial positioning.
2. Run `SIPX_ASTERISK_INTEGRATION=1 python -m pytest apps/asterisk/tests/test_asterisk_integration.py` after starting `docker/asterisk`.
3. Add richer fake media events, recording/transcript artifacts, and retention policy.
4. Add RTP media send/receive, RFC4733 DTMF over RTP, then live SIP inspector and advanced RTP/media runtime behavior.
5. Decide whether generic OpenAI-compatible LLM support is enough for the next AI block or whether to add a provider protocol before vendor-specific adapters.

## Risks

- Scope is large; keep MVP focused on harness core + one backend path.
- Asterisk can hide raw SIP details; do not use it for conformance claims without capture or NativeSipBackend.
- AI semantic assertions are probabilistic; do not make them sole critical-pass criterion.
- Recordings/transcripts are sensitive; design redaction/retention before real deployments.
- `python -m ty check` is unavailable in the system interpreter; configured validation uses `uv run ty check`, which passes.
- Redaction exists but retention policy and transcript/recording-specific metadata handling are still open.
- T21-T23 native SIP signaling, headless softphone, and lab hooks are complete; advanced media wiring and runtime behavior remain pending.
- T9-T11, T15, and T28 Asterisk ARI control-plane, timeline mapping, WebSocket media MVP, inbound Stasis example, and Docker lab are complete; real Asterisk integration tests are guarded by env and not run by default.
- GitHub workflows are added but not executed locally; local validation covered their referenced Python commands, while Docker remains unavailable in this WSL environment.
- RTP and DTMF primitives exist, but jitter buffer, RTCP, impairment, and media clock are not implemented yet.
- SIP INFO DTMF is implemented for confirmed native calls; RTP RFC4733 DTMF send from the softphone remains future media runtime work.
- LLM live validation requires `SIPX_LLM_API_KEY`; default local tests deliberately skip real provider calls.

## Open Questions

- License choice before public release is still open.
- Next advanced media/runtime priority is still open: recordings/transcripts, jitter/RTCP/impairment, or AI slow-path behavior.
- GitHub release draft policy after `1.2.0` should keep only the latest draft release before publishing.
- LLM provider scope after the OpenAI-compatible template is still open.
