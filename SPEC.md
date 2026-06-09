# SPEC

## §G

G1: `sipx` = Python Voice/SIP Harness for scenarios, `expect`, timeline, artifacts, AI, technical softphone, IVR, queues, contact center, SIP/RTP/media validation.
G2: neutral core + backends: `AsteriskBackend` first for fast MVP; `NativeSipBackend` required for wire-level control.
G3: product = Harness; Asterisk = backend; native SIP = low-level engine.

## §C

C1: runtime Python `>=3.14` per `pyproject.toml`.
C2: product != Asterisk wrapper; Asterisk = backend, Harness = core.
C3: MVP ! Asterisk-backed: ARI, Stasis, bridges, recordings, ExternalMedia/WebSocket/AudioSocket.
C4: Native SIP ! exist for technical softphone, fuzzing, negative tests, raw SIP/SDP/RTP.
C5: public API ! backend-independent.
C6: `Actor`, `Scenario`, `Expect`, `Timeline`, `Verdict`, `Artifact`, `CallLeg` ! central concepts.
C7: native SIP core ! sans-I/O; sockets/timers live in async runtime.
C8: RTP/media ! streaming; STT/TTS/LLM ⊥ block media loop.
C9: deterministic/temporal asserts ! critical regression base; semantic AI = supplemental/probabilistic.
C10: Asterisk GPLv2 ∴ Python as separate process; ⊥ Asterisk loadable module in MVP.
C11: G.711 ⊥ depend on `audioop`; Python 3.13+ removed module.
C12: logs/artifacts ! redact `Authorization`, tokens, passwords, SDP crypto, configured PII.
C13: import/package name = `sipx`; CLI command = `sipx`.
C14: technical softphone ! built on `NativeSipBackend`, not on Asterisk.
C15: PJSIP/PJSUA2 = optional future backend; not core harness foundation.
C16: softphone engine ! headless first; UI/CLI/TUI clients later consume engine.
C17: maintained English files in current structure are source of truth; `IDEA.md` = historical source only; no separate `docs/` tree.

## §I

api: `Harness` → creates actors, runs scenarios, collects timeline/verdict/artifacts.
api: `Actor` → `softphone`, `asterisk`, `remote`, `ai_agent`, `fake_carrier`, `queue`.
api: `Scenario` → steps async + fixtures + expectations + verdict.
api: `expect(target)` → temporal/deterministic/probabilistic/statistical matchers.
api: `Call` → `answer`, `hangup`, `say`, `play`, `collect`, `send_dtmf`, `bridge`, `events`.
api: `CallLeg` → SIP dialog/channel + media session + per-leg artifacts.
api: `CallControl` → `call`, `answer`, `hangup`, `send_dtmf`, `bridge`.
api: `SipWireControl` → `send_request`, `send_response`, raw SIP event stream.
api: `MediaControl` → `start`, `recv_frame`, `send_frame`, `send_dtmf`.
api: `Timeline` → monotonic JSONL events with actor/call/leg/category/name/data.
api: `Verdict` → `passed|failed|error|skipped` + reason + failed expectations + metrics + artifacts.
api: `Artifact` → `timeline.jsonl`, `recording.wav`, `transcript.json`, `sip.pcap`, `report.html`.
api: `ScenarioRecorder` → manual call/timeline/actions → YAML/Python scenario.
api: `Profile` → strict/lab/account/media/SIP override config.
backend: `AsteriskBackend` → ARI REST/WS, Stasis, channels, bridges, playback, DTMF, recordings.
backend: `AsteriskMediaPort` → WebSocket media | AudioSocket | ExternalMedia RTP.
backend: `NativeSipBackend` → own SIP/SDP/RTP/DTMF, modes `strict|lab`.
backend: `PjsipBackend` → optional future robust softphone backend; less suitable for malformed/wire-level tests.
backend: `MockBackend` → CI/unit without network.
backend: `ReplayBackend` → replays timeline/artifacts.
cfg: `harness.toml` → backends, profiles, accounts, media, artifacts.
doc: `README.md` → product orientation + source-of-truth map.
doc: `DESIGN.md` → full detailed implementation context: product, API, backends, protocols, media/AI, softphone, Asterisk, roadmap.
doc: `TODO.md` → executable roadmap.
doc: `.spec/state.md` → current project state.
doc: `.spec/handoff.md` → handoff/read order.
doc: `.mem/hot.md` → compact durable facts.
doc: `.mem/decisions.md` → accepted decisions.
doc: `.mem/open-loops.md` → unresolved choices.
cmd: `sipx scenario run <file>` → verdict + artifacts.
cmd: `sipx profile list|show` → inspect `harness.toml` profiles.
cmd: `sipx phone register [profile]` → registered headless softphone.
cmd: `sipx phone unregister [profile]` → unregister headless softphone.
cmd: `sipx phone call <target>` → manual/automated outbound call.
cmd: `sipx phone listen [profile]` → answer inbound call.
cmd: `sipx register|unregister|call|listen` → top-level operational aliases.
cmd: `sipx options <target>` → SIP OPTIONS probe over UDP.
cmd: `sipx message <target> [text]` → SIP MESSAGE over UDP.
cmd: `sipx request <method> <target>` → generic SIP request over UDP with headers/body flags.
cmd: `sipx replay <timeline.jsonl>` → replay/inspection.
ci: `.github/workflows/ci.yml` → uv sync, console-script smoke, ruff, pytest, build.
ci: `.github/workflows/asterisk.yml` → Docker Asterisk lab + opt-in integration tests.
ci: `.github/workflows/create-release.yml` → draft `v<pyproject version>` release on `master`.
ci: `.github/workflows/release.yml` → verify tag, test/build, PyPI trusted publish.
proto: SIP RFC 3261, SDP RFC 8866, Offer/Answer RFC 3264, RTP/RTCP RFC 3550/3551, DTMF RFC 4733.
proto: Asterisk ARI/Stasis, ExternalMedia, AudioSocket, chan_websocket, PJSIP.

## §V

V1: public API uses `Harness/Actor/Scenario/Expect/Timeline/Verdict/Artifact`; backend = internal detail.
V2: ∀ backend → declares capabilities; expectation without capability → `UnsupportedExpectation`, not false pass.
V3: ∀ relevant event → monotonic `TimelineEvent` with actor/call/leg/category/name/data.
V4: ∀ scenario run → `Verdict` first-class; failure includes evidence/artifacts, not just exception.
V5: critical regression ! at least 1 deterministic/temporal assert; semantic AI ⊥ sole criterion.
V6: `AsteriskBackend` ⊥ promise exact SIP wire-level behavior without capture/passive evidence.
V7: `NativeSipBackend` core parser/serializer/txn/dialog/SDP/RTP ! sans-I/O.
V8: SIP/SDP/RTP parsers ! size limits + typed errors + fail-closed; ⊥ crash/OOM loop.
V9: `Call` ! support `CallLeg` + `MediaBridge`; queue/transfer/B2BUA do not collapse into single call.
V10: media loop ⊥ call STT/TTS/LLM synchronously; backpressure/silence/placeholder when AI is slow.
V11: internal DTMF = media event; RFC 4733 primary; SIP INFO/in-band optional.
V12: MVP codecs = PCMU/PCMA + internal PCM; `audioop` ⊥ dependency.
V13: artifacts/logs ! redact secrets/configured PII before persistence.
V14: Asterisk control ! ARI/Stasis; AGI/AMI auxiliary, not harness core.
V15: `strict` mode follows RFC/interoperability; `lab` mode allows controlled overrides/malformed behavior.
V16: every scenario ! minimum artifacts: timeline + verdict; recording/transcript/pcap/report optional by config.
V17: technical softphone ! use `NativeSipBackend`; Asterisk can be backend/SUT/resource, not softphone foundation.
V18: `NativeSipBackend` ! expose `SipWireControl`; `AsteriskBackend` may not.
V19: technical softphone ! scenario recorder/export from timeline + user actions.
V20: lab hooks ! available before send/after receive/before SDP for protocol manipulation.
V21: profiles ! separate strict real interop from lab fault-injection behavior.
V22: mixed scenario ! support native actors + Asterisk actors + remote targets in one timeline.
V23: implementation work ! rely on maintained current-structure docs; `IDEA.md` and `/docs` must not be required for context.
V24: `cmd: sipx` ! runnable via package-manager console script from repo root.
V25: operational softphone CLI ! build `NativeSoftphoneConfig` from profile or explicit account args; tests must not require network.
V26: GitHub workflows ! use current project metadata/commands; ⊥ old `_version.py`, old Python pin, or task-only aliases.
V27: phone CLI network commands ! fail before network unless profile or explicit SIP identity exists; help must show required account flags/examples.
V28: curl-like SIP CLI ! require explicit From identity, support headers/body flags, and derive remote from target/registrar/profile without silent localhost default.
V29: SIP auth ! INVITE/raw request receiving `401|407` retries once with Digest when credentials exist; retry waits for current CSeq response; secrets ⊥ logs/docs/artifacts.
V30: SIP debug CLI ! packet visibility shows every sent/received datagram; Authorization secrets redacted; works in strict mode.
V31: operational softphone call ! outbound INVITE includes SDP audio offer, opens advertised RTP UDP port, and validates `2xx` SDP answer before confirmed.
V32: LLM integrations ! external provider keys only via environment/runtime injection; tests/examples ⊥ hardcoded private keys or proxy data.
V33: validation gate ! `uv run ty check` passes before an implementation block is complete; system-interpreter tool absence is reported separately.
V34: operational DTMF ! confirmed native calls can send DTMF via SIP INFO `application/dtmf-relay`; CLI examples show call, OPTIONS, MESSAGE, INFO, and DTMF flows without hardcoded private secrets.

## §T

id|status|task|cites
---|---|---|---
T1|x|update README/metadata: `sipx` identity, Python >=3.14, harness positioning|G1,C1,C13
T2|x|create base package `sipx.core`: events, timeline, verdict, artifacts, metrics|V1,V3,V4,V16
T3|x|define `BackendCapability` + `UnsupportedExpectation` error|V2,V6
T4|x|implement `Harness`, `Actor`, `Scenario` async skeleton|V1,I.api
T5|x|implement JSONL timeline + actor/call/leg correlation|V3,I.api
T6|x|implement result/verdict/artifact model|V4,V16
T7|x|implement `expect()` core: within/during/not_before + rich failure|V4,V5,I.api
T8|x|create `MockBackend` for unit tests without network|I.backend
T9|x|create `AsteriskBackend` async ARI client + WebSocket events|V14,I.backend
T10|x|map ARI channels/bridges/playback/hangup/DTMF to timeline|V3,V14
T11|x|add Asterisk media port: choose WebSocket/AudioSocket/ExternalMedia MVP|C3,V10,I.backend
T12|x|define `AudioFrame`, `MediaPort`, STT/TTS protocols and barge-in policy|V10,V11,I.api
T13|x|create scenario runner + artifacts directory layout|V4,V16,I.cmd
T14|x|add minimal CLI `sipx scenario run`|I.cmd,T13
T15|x|implement inbound Asterisk app via Stasis example|C3,V14
T16|x|implement `NativeSipBackend` SIP parser/serializer sans-I/O|C4,V7,V8
T17|x|implement robust URI/HeaderMap/Content-Length + tests|V8,T16
T18|x|implement SDP model/parser/offer-answer audio PCMU/PCMA/telephone-event|V7,V11,V12
T19|x|implement RTP packet parse/serialize + seq/timestamp/SSRC stats|V7,V8,V12
T20|x|implement DTMF RFC4733 encoder/decoder + event model|V11,T19
T21|x|implement basic UAC/UAS INVITE/ACK/BYE/CANCEL/REGISTER|C4,V7,V15
T22|x|implement headless technical softphone on `NativeSipBackend`|G1,C4,V15,V17
T23|x|add lab hooks for headers/SDP/timers/malformed SIP|V15,V20,T22
T24|x|add recorder/export scenario from timeline + user actions|V16,V19,I.artifact
T25|x|add HTML/text reports with timeline, SIP, RTP, transcript, verdict|V4,V16
T26|x|add fuzz/property tests for SIP/SDP/RTP/DTMF parsers|V8,T16,T18,T19,T20
T27|x|add central redaction for logs/artifacts|V13
T28|x|add interop lab with Asterisk 22 LTS and basic scenarios|C3,V14
T29|x|add profile config for strict/lab/account/media overrides|V15,V21,I.api
T30|x|add mixed scenario support: native caller + Asterisk backend + native agent|V22,I.api
T31|x|document optional future `PjsipBackend` tradeoffs|C15,I.backend
T32|x|consolidate detailed implementation context into current structure, not `/docs`|C17,V23
T33|x|add operational softphone/profile CLI commands plus no-network CLI tests|V17,V21,V24,V25,I.cmd
T34|x|adapt GitHub CI, Asterisk integration, draft release, and PyPI publish workflows|V24,V26,I.ci
T35|x|backprop phone CLI missing-config UX: no silent localhost network defaults|V25,V27,I.cmd
T36|x|add curl-like SIP `options`, `message`, and generic `request` CLI|V24,V27,V28,I.cmd
T37|x|add Digest retry for INVITE calls and raw SIP request CLI with CSeq-scoped response matching|V27,V28,V29,I.cmd
T38|x|add redacted `--debug-sip` packet visibility for phone and raw SIP CLI|V13,V24,V25,V28,V30,I.cmd
T39|x|add native softphone SDP offer/answer negotiation and media CLI flags|V17,V25,V31,I.cmd
T40|x|add opt-in generic OpenAI-compatible LLM client/tests and LLM/native/Asterisk examples|V13,V23,V32,I.api
T41|x|clear baseline type-check diagnostics for current implementation surfaces|V33,I.ci
T42|x|add in-dialog SIP INFO DTMF support plus richer native CLI/Python examples|V13,V25,V30,V31,V34,I.cmd

## §B

id|date|cause|fix
---|---|---|---
B1|2026-06-08|tests used `pytest.mark.asyncio` but active `pytest` lacked async plugin|tests use `asyncio.run`; no new §V, product spec unchanged
B2|2026-06-08|redaction regex replacement assumed every secret pattern had capture group|fix replacement helper; covered by V13
B3|2026-06-08|retransmission timer code used `asyncio` without module import|focused runtime tests caught it; no new §V, mechanical import failure
B4|2026-06-08|`uv run sipx` had no installable build backend, so uv ran `sipx/__main__.py` directly and imports failed|V24
B5|2026-06-08|`sipx register` without profile/flags silently used localhost defaults and timed out|V27
B6|2026-06-08|real proxy INVITE returned `401 Unauthorized`; call path accepted credentials but never retried Digest auth|V29
B7|2026-06-08|authenticated real proxy INVITE reached `603 Declined`; outbound softphone INVITE had no SDP offer or open RTP port|V31
B8|2026-06-08|`uv run ty check` baseline had 29 diagnostics from dynamic call, mapping, URI, SDP, and media frame typing|V33
B9|2026-06-08|DTMF implementation added helper/softphone call path but backend method/import was incomplete during focused validation|V34
