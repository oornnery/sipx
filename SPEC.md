# SPEC

## §G

G1: `sipx` workspace = Python Voice/SIP toolkit: root SIP protocol/runtime + `sipx-harness` scenarios/timeline/artifacts + app packages.
G2: root `sipx` = SIP/SDP/RTP/media primitives + SIP UAC/UAS runtime; `sipx-harness` = Harness/Actor/Scenario/Timeline/Verdict/Artifact/runtimes/redaction.
G3: product = Harness workspace; Asterisk = `AsteriskRuntime`; SIP UAC/UAS runtime = low-level engine.

## §C

C1: runtime Python `>=3.14` per `pyproject.toml`.
C2: product != Asterisk wrapper; Asterisk = runtime app, Harness = `sipx-harness`.
C3: MVP ! Asterisk runtime: ARI, Stasis, bridges, recordings, ExternalMedia/WebSocket/AudioSocket.
C4: SIP UAC/UAS runtime ! exist for technical softphone, fuzzing, negative tests, raw SIP/SDP/RTP.
C5: public API ! separated by package: root SIP-only; harness API in `sipx_harness`; apps in `apps/*`.
C6: `Actor`, `Scenario`, `Expect`, `Timeline`, `Verdict`, `Artifact`, `CallLeg` ! central `sipx_harness` concepts.
C7: SIP core ! sans-I/O; sockets/timers live in async runtime.
C8: RTP/media ! streaming; STT/TTS/LLM ⊥ block media loop.
C9: deterministic/temporal asserts ! critical regression base; semantic AI = supplemental/probabilistic.
C10: Asterisk GPLv2 ∴ Python as separate process; ⊥ Asterisk loadable module in MVP.
C11: G.711 ⊥ depend on `audioop`; Python 3.13+ removed module.
C12: logs/artifacts ! redact `Authorization`, tokens, passwords, SDP crypto, configured PII.
C13: import/package name = `sipx`; CLI command = `sipx`.
C14: technical softphone ! built on `SipUserAgent`/`SipUac`/`SipUas`, not on Asterisk.
C15: PJSIP/PJSUA2 = optional future runtime; not core harness foundation.
C16: softphone engine ! headless first; UI/CLI/TUI clients later consume engine.
C17: maintained English files in current structure are source of truth; `IDEA.md` = historical source only; no separate `docs/` tree.
C18: root package `sipx` ! SIP-only: SIP/SDP/RTP/media primitives + SIP UAC/UAS runtime + direct SIP examples; ⊥ Harness/Mock/Timeline/Scenario/redaction, LLM, softphone wrapper, Asterisk runtime, or CLI.
C19: app surfaces live under `apps/*` as independent `uv` workspace packages that import `sipx` via workspace dependency.
C20: root `pytest` ! collect core `tests/` only; app package tests under `apps/*/tests` are opt-in by explicit path/package.
C21: public names ! use `runtime` for harness/Asterisk/mock and `user_agent` for `SipUserAgent`; generic `backend` allowed only packaging metadata like `build-backend`.
C22: speech adapter protocols ! live in `apps/stt` / `apps/tts`; root `sipx.media` keeps generic audio frames, ports, and barge-in only.
C23: `SipUac`/`SipUas` ! own high-level SIP phone ergonomics; `SipSoftphone` package/concept ⊥.
C24: core CLI `sipx` ! SIP/RTP-only curl/httpx-cli shape; harness/scenario/profile/replay CLI ⊥ root command.
C25: PyAudio ? optional extra only; root install dependencies stay native-free by default.
C26: RTP audio ! support synthetic `silence|noise` without media device; still opens RTP socket when SDP audio active.

## §I

api: `sipx_harness.Harness` → creates actors, runs scenarios, collects timeline/verdict/artifacts.
api: `sipx_harness.Actor` → `softphone`, `asterisk`, `remote`, `ai_agent`, `fake_carrier`, `queue`.
api: `sipx_harness.Scenario` → steps async + fixtures + expectations + verdict.
api: `sipx_harness.expect(target)` → temporal/deterministic/probabilistic/statistical matchers.
api: `sipx_harness.Call` → `answer`, `hangup`, `say`, `play`, `collect`, `send_dtmf`, `bridge`, `events`.
api: `sipx_harness.CallLeg` → SIP dialog/channel + media session + per-leg artifacts.
api: `CallControl` → `call`, `answer`, `hangup`, `send_dtmf`, `bridge`.
api: `SipWireControl` → `send_request`, `send_response`, raw SIP event stream.
api: `MediaControl` → `start`, `recv_frame`, `send_frame`, `send_dtmf`.
api: `sipx_harness.Timeline` → monotonic JSONL events with actor/call/leg/category/name/data.
api: `sipx_harness.Verdict` → `passed|failed|error|skipped` + reason + failed expectations + metrics + artifacts.
api: `sipx_harness.Artifact` → `timeline.jsonl`, `recording.wav`, `transcript.json`, `sip.pcap`, `report.html`.
api: `sipx_harness.ScenarioRecorder` → manual call/timeline/actions → YAML/Python scenario.
api: `sipx_harness.Profile` → strict/lab/account/media/SIP override config.
api: `Runtime` / `CallRuntime` / `DtmfRuntime` → harness runtime ABC contracts.
api: `SipWireRuntime` / `SipUacRuntime` / `SipUasRuntime` → SIP runtime role ABC contracts.
runtime: `AsteriskRuntime` → ARI REST/WS, Stasis, channels, bridges, playback, DTMF, recordings.
runtime: `AsteriskMediaPort` → WebSocket media | AudioSocket | ExternalMedia RTP.
runtime: `SipUserAgent`/`SipUac`/`SipUas` → own SIP/SDP/RTP/DTMF, modes `strict|lab`.
runtime: `PjsipRuntime` → optional future robust softphone runtime; less suitable for malformed/wire-level tests.
runtime: `MockRuntime` → CI/unit without network.
runtime: `ReplayRuntime` → replays timeline/artifacts.
api: `SipUac` → high-level outbound `register`, `unregister`, `options`, `message`, `request`, `call`.
api: `SipUas` → high-level inbound `listen`, `answer`, `reject`, `answer_bye`, re-INVITE handling.
api: `SipCall` → `hangup`, `send_dtmf`, `mute_send`, `unmute_send`, `hold`, `resume`, `metrics`.
api: `SipProvisionalResponse` → configured INVITE `1xx` response: status/reason/body/content-type.
api: `event_hooks` → httpx-style dict of event name to list of callables; events: `request`, `response`, `wire`, `sdp`, `retransmission`; side-effect only; `sdp` and `retransmission` require lab mode.
api: `Sip*Summary` → dataclass snapshots for request/response/call/SDP output and JSON export.
api: `SipCapabilities` → explicit `Accept`/`Allow`/`Allow-Events`/`Supported` header declaration; no implicit unsupported features.
api: `RtpAudioSession` → UDP RTP send/receive, codec encode/decode, jitter buffer, metrics snapshot.
api: `RtpJitterBuffer` → ordered playout frames + underrun/late/drop metrics.
api: `RtpMetricsSnapshot` → RTP tx/rx/loss/jitter/buffer/audio counters.
cfg: `harness.toml` → runtimes, profiles, accounts, media, artifacts.
doc: `README.md` → product orientation + source-of-truth map.
doc: `DESIGN.md` → full detailed implementation context: product, API, runtimes, protocols, media/AI, softphone, Asterisk, roadmap.
doc: `TODO.md` → executable roadmap.
doc: `.spec/state.md` → current project state.
doc: `.spec/handoff.md` → handoff/read order.
doc: `.mem/hot.md` → compact durable facts.
doc: `.mem/decisions.md` → accepted decisions.
doc: `.mem/open-loops.md` → unresolved choices.
cmd: `sipx register|unregister|call|listen` → SIP/RTP account/call commands.
cmd: `sipx options <target>` → SIP OPTIONS probe over UDP.
cmd: `sipx message <target> [text]` → SIP MESSAGE over UDP.
cmd: `sipx request <method> <target>` → generic SIP request over UDP with headers/body flags.
cmd: `sipx request|options|message ... --print-message --compact-headers` → render SIP message without network.
cmd: `sipx call <uri> --audio none|silence|noise|pyaudio --rtp-stats --metrics-json <path>` → SIP call + RTP media metrics.
cmd: `sipx listen --audio none|silence|noise|pyaudio --jitter-buffer-ms <n>` → inbound SIP answer + RTP media metrics.
ci: `.github/workflows/ci.yml` → uv sync, console-script smoke, ruff, pytest, build.
ci: `.github/workflows/asterisk.yml` → Docker Asterisk lab + opt-in integration tests.
ci: `.github/workflows/create-release.yml` → draft `v<pyproject version>` release on `master`.
ci: `.github/workflows/release.yml` → verify tag, test/build, PyPI trusted publish.
proto: SIP RFC 3261, SDP RFC 8866, Offer/Answer RFC 3264, RTP/RTCP RFC 3550/3551, DTMF RFC 4733.
proto: Asterisk ARI/Stasis, ExternalMedia, AudioSocket, chan_websocket, PJSIP.
pkg: root `sipx` → SIP protocol/runtime package + direct SIP examples only.
pkg: `sipx.examples` → direct SIP scripts defaulting to the public Mizu demo via generic SIP env vars; no argparse, no app deps.
pkg: `apps/harness` → `sipx-harness` / `sipx_harness` Harness, scenarios, timeline, verdicts, artifacts, profiles, reports, test runtimes.
pkg: `apps/llm` → `sipx-llm` / `sipx_llm` generic LLM client and LLM examples/tests.
pkg: `apps/asterisk` → `sipx-asterisk` / `sipx_asterisk` Asterisk ARI runtime, Stasis helpers, Docker-facing tests/templates.
pkg: `apps/cli` → `sipx-cli` / `sipx_cli` console command `sipx`.
pkg: `apps/scenarios` → `sipx-scenarios` / `sipx_scenarios` runnable scenario/SIP example library.
pkg: `apps/stt`, `apps/tts` → speech protocol/adapter slots for future providers; root keeps generic media primitives only.

## §V

V1: `sipx_harness` public API uses `Harness/Actor/Scenario/Expect/Timeline/Verdict/Artifact`; runtime = internal detail.
V2: ∀ runtime → declares capabilities; expectation without capability → `UnsupportedExpectation`, not false pass.
V3: ∀ relevant event → monotonic `TimelineEvent` with actor/call/leg/category/name/data.
V4: ∀ scenario run → `Verdict` first-class; failure includes evidence/artifacts, not just exception.
V5: critical regression ! at least 1 deterministic/temporal assert; semantic AI ⊥ sole criterion.
V6: `AsteriskRuntime` ⊥ promise exact SIP wire-level behavior without capture/passive evidence.
V7: SIP core parser/serializer/txn/dialog/SDP/RTP ! sans-I/O.
V8: SIP/SDP/RTP parsers ! size limits + typed errors + fail-closed; ⊥ crash/OOM loop.
V9: `Call` ! support `CallLeg` + `MediaBridge`; queue/transfer/B2BUA do not collapse into single call.
V10: media loop ⊥ call STT/TTS/LLM synchronously; backpressure/silence/placeholder when AI is slow.
V11: internal DTMF = media event; RFC 4733 primary; SIP INFO/in-band optional.
V12: MVP codecs = PCMU/PCMA + internal PCM; `audioop` ⊥ dependency.
V13: artifacts/logs ! redact secrets/configured PII before persistence.
V14: Asterisk control ! ARI/Stasis; AGI/AMI auxiliary, not harness core.
V15: `strict` mode follows RFC/interoperability; `lab` mode allows controlled overrides/malformed behavior.
V16: every scenario ! minimum artifacts: timeline + verdict; recording/transcript/pcap/report optional by config.
V17: technical softphone ! use `SipUserAgent`/`SipUac`/`SipUas`; Asterisk can be runtime/SUT/resource, not softphone foundation.
V18: `SipUserAgent` ! expose `SipWireControl`; `AsteriskRuntime` may not.
V19: technical softphone ! scenario recorder/export from timeline + user actions.
V20: lab hooks ! available before send/after receive/before SDP for protocol manipulation.
V21: profiles ! separate strict real interop from lab fault-injection behavior.
V22: mixed scenario ! support SIP actors + Asterisk actors + remote targets in one timeline.
V23: implementation work ! rely on maintained current-structure docs; `IDEA.md` and `/docs` must not be required for context.
V24: `cmd: sipx` ! runnable via package-manager console script from repo root.
V25: operational SIP CLI ! build `SipUac`/`SipUas` config from profile or explicit account args; tests must not require network.
V26: GitHub workflows ! use current project metadata/commands; ⊥ old `_version.py`, old Python pin, or task-only aliases.
V27: phone CLI network commands ! fail before network unless profile or explicit SIP identity exists; help must show required account flags/examples.
V28: curl-like SIP CLI ! require explicit From identity, support headers/body flags, and derive remote from target/registrar/profile without silent localhost default.
V29: SIP auth ! INVITE/raw request receiving `401|407` retries once with Digest when credentials exist; retry waits for current CSeq response; secrets ⊥ logs/docs/artifacts.
V30: SIP debug CLI ! packet visibility shows every sent/received datagram; Authorization secrets redacted; works in strict mode.
V31: operational softphone call ! outbound INVITE includes SDP audio offer, opens advertised RTP UDP port, and validates `2xx` SDP answer before confirmed.
V32: LLM integrations ! external provider keys only via environment/runtime injection; tests/examples ⊥ hardcoded private keys or proxy data.
V33: validation gate ! `uv run ty check` passes before an implementation block is complete; system-interpreter tool absence is reported separately.
V34: operational DTMF ! confirmed SIP calls can send DTMF via SIP INFO `application/dtmf-relay`; CLI examples show call, OPTIONS, MESSAGE, INFO, and DTMF flows without hardcoded private secrets.
V35: LLM env config ! missing optional `SIPX_LLM_*` vars use concrete defaults; no dataclass descriptors or internal objects leak into runtime parsing.
V36: LLM SIP audit examples ! runnable directly and via `sipx scenario run`; output structured behavior/risk/findings/actions while deterministic SIP checks remain separate from LLM judgment.
V37: LLM SIP audit security ! redacted auth markers are accepted; unredacted `Authorization`/`Proxy-Authorization` values are flagged before LLM analysis.
V38: SIP auth ! confirmed SIP calls receiving `401|407` to in-dialog `BYE` retry once with Digest when credentials exist; retry waits for current BYE CSeq response; secrets ⊥ logs/docs/artifacts.
V39: package boundaries ! importing root `sipx` does not import/export Harness, Mock, Timeline, Scenario, LLM, softphone, Asterisk, CLI, or app examples.
V40: workspace apps ! each `apps/*` package has own `pyproject.toml`, imports `sipx` as workspace dependency, and exposes app tests/examples without mutating root core package.
V41: CLI ownership ! console command `sipx` belongs to `apps/cli`; root core package has no console script and no `sipx.cli` module.
V42: public SIP runtime naming ! use `SipUserAgent`, `SipUac`, `SipUas`, `SipCall`, and `SipRetransmissionPolicy`; `Native*` runtime aliases ⊥.
V43: INVITE UAC timeout ! before first matching `1xx|2xx|3xx|4xx|5xx`, `timeout` detects no response; after matching provisional `1xx`, call waits for final response or caller cancellation, not `SipUdpError` no-datagram timeout.
V44: test boundary ! `python -m pytest`/`uv run pytest` from root runs core `sipx` tests only; app tests require explicit app path/package.
V45: runtime contracts ! `MockRuntime` implements harness call-control/DTMF ABCs; `SipUserAgent` implements SIP wire/UAC/UAS ABCs; capability checks remain fail-loud.
V46: ABC contracts ! method signatures match concrete implementations closely enough for `uv run ty check`; generic `**kwargs` abstract methods ⊥ when concrete methods require keyword-only params.
V47: harness symbols (`Harness`, `Timeline`, `MockRuntime`, `RuntimeCapability`) ! import from `sipx_harness`; root `sipx` ⊥ export them.
V48: public runtime naming ! no `Native*` aliases and no `Backend*` API identifiers; use `AsteriskRuntime`, `MockRuntime`, `RuntimeCapability`, and `user_agent` for `SipUserAgent` injection.
V49: root `sipx` / `sipx.media` ⊥ export `SttEngine`, `SttStream`, `TranscriptEvent`, or `TtsEngine`; speech protocols import from `sipx_stt` / `sipx_tts`.
V50: redaction ! preserve safe evidence shape (`Header: [REDACTED]`, `a=crypto: [REDACTED]`) while removing secret values.
V51: generic `Redactor` / `default_redactor` ! import from `sipx_harness`; root `sipx` / `sipx.security` ⊥ export or contain generic artifact/app redaction.
V52: `SipUac`/`SipUas` high-level APIs ! live in `sipx/uac.py` and `sipx/uas.py`; `SipUserAgent` remains shared SIP transport/dialog engine.
V53: `SipSoftphone*` public API/package ⊥; softphone ergonomics move to `SipUac`/`SipUas` with no duplicated SIP transaction/auth logic.
V54: root CLI `sipx` ! SIP/RTP curl-like only; scenario/profile/replay commands move out of root CLI surface.
V55: RTP audio modes ! `none|silence|noise|pyaudio`; `silence|noise` use synthetic PCM and no device open; `pyaudio` lazy-imports optional dependency.
V56: RTP metrics ! expose tx/rx packets, bytes, loss, duplicates, out-of-order, late drops, parse/decode errors, jitter ms, selected codec, payload type.
V57: RTP jitter buffer ! configurable target/max ms; ordered playout; underrun, overrun, duplicate, late, concealment, resync counters.
V58: call metrics ! expose SIP response timing, auth retry/retransmission counts, SDP selected codec/direction, call duration, RTP summary.
V59: SDP media address ! separate RTP bind address from advertised SDP address; no SIP port fallback for RTP media.
V60: G.711 ! PCMU/PCMA encode/decode without `audioop`; synthetic noise/silence verify real RTP payloads.
V61: G.711 decoded synthetic silence ! near-zero PCM amplitude; exact zero ⊥ required after companding.
V62: INVITE UAS provisionals ! support `0+` configured `SipProvisionalResponse` before final response; default = `180 Ringing`; direct final response valid.
V63: `100 Trying` provisional ! no SDP body, no Contact, no To tag; `180|183|199` may create early dialog with To tag.
V64: root `sipx.examples.*` ! direct SIP-only examples; no argparse; account/routing via generic `SIPX_*` env vars; provider-prefixed env names ⊥; no imports from `apps/*` or `sipx_harness`.
V65: `sipx.examples` call probes ! explicit `SIPX_TARGET` before network + total wait bounded by `SIPX_TIMEOUT`; structured JSON on config/call/timeout error; traceback/hang ⊥.
V66: summaries ! return dataclass snapshots; JSON conversion happens at CLI/example edge.
V67: SIP request auth/matching ! owned by `SipUserAgent.request`; CLI/examples ⊥ duplicate Digest challenge or CSeq response matching.
V68: compact headers ! parser expands compact names; serializer ? compact when explicitly requested; default canonical.
V69: SIP advertised capabilities ! explicit user/config input only; ⊥ claim unsupported `Allow`/`Allow-Events` features by default.
V70: event_hooks ! httpx-style dict; `sdp` and `retransmission` events require lab mode; all hooks are side-effect only (return value ignored).
V71: RTP wire events ! expose tx/rx `RtpWireEvent` with direction, remote, raw bytes, parsed packet, and optional parse error; `event_hooks["rtp"]` fire on every RTP send/receive across all audio modes.

## §T

id|status|task|cites
---|---|---|---
T1|x|update README/metadata: `sipx` identity, Python >=3.14, harness positioning|G1,C1,C13
T2|x|create base package `sipx.core`: events, timeline, verdict, artifacts, metrics|V1,V3,V4,V16
T3|x|define `RuntimeCapability` + `UnsupportedExpectation` error|V2,V6
T4|x|implement `Harness`, `Actor`, `Scenario` async skeleton|V1,I.api
T5|x|implement JSONL timeline + actor/call/leg correlation|V3,I.api
T6|x|implement result/verdict/artifact model|V4,V16
T7|x|implement `expect()` core: within/during/not_before + rich failure|V4,V5,I.api
T8|x|create `MockRuntime` for unit tests without network|I.runtime
T9|x|create `AsteriskRuntime` async ARI client + WebSocket events|V14,I.runtime
T10|x|map ARI channels/bridges/playback/hangup/DTMF to timeline|V3,V14
T11|x|add Asterisk media port: choose WebSocket/AudioSocket/ExternalMedia MVP|C3,V10,I.runtime
T12|x|define `AudioFrame`, `MediaPort`, and barge-in policy|V10,V11,I.api
T13|x|create scenario runner + artifacts directory layout|V4,V16,I.cmd
T14|x|add minimal CLI `sipx scenario run`|I.cmd,T13
T15|x|implement inbound Asterisk app via Stasis example|C3,V14
T16|x|implement SIP parser/serializer sans-I/O|C4,V7,V8
T17|x|implement robust URI/HeaderMap/Content-Length + tests|V8,T16
T18|x|implement SDP model/parser/offer-answer audio PCMU/PCMA/telephone-event|V7,V11,V12
T19|x|implement RTP packet parse/serialize + seq/timestamp/SSRC stats|V7,V8,V12
T20|x|implement DTMF RFC4733 encoder/decoder + event model|V11,T19
T21|x|implement basic UAC/UAS INVITE/ACK/BYE/CANCEL/REGISTER|C4,V7,V15
T22|x|implement headless technical softphone on `SipUserAgent`|G1,C4,V15,V17
T23|x|add lab hooks for headers/SDP/timers/malformed SIP|V15,V20,T22
T24|x|add recorder/export scenario from timeline + user actions|V16,V19,I.artifact
T25|x|add HTML/text reports with timeline, SIP, RTP, transcript, verdict|V4,V16
T26|x|add fuzz/property tests for SIP/SDP/RTP/DTMF parsers|V8,T16,T18,T19,T20
T27|x|add central redaction for harness logs/artifacts|V13
T28|x|add interop lab with Asterisk 22 LTS and basic scenarios|C3,V14
T29|x|add profile config for strict/lab/account/media overrides|V15,V21,I.api
T30|x|add mixed scenario support: SIP caller + Asterisk runtime + SIP agent|V22,I.api
T31|x|document optional future `PjsipRuntime` tradeoffs|C15,I.runtime
T32|x|consolidate detailed implementation context into current structure, not `/docs`|C17,V23
T33|x|add operational softphone/profile CLI commands plus no-network CLI tests|V17,V21,V24,V25,I.cmd
T34|x|adapt GitHub CI, Asterisk integration, draft release, and PyPI publish workflows|V24,V26,I.ci
T35|x|backprop phone CLI missing-config UX: no silent localhost network defaults|V25,V27,I.cmd
T36|x|add curl-like SIP `options`, `message`, and generic `request` CLI|V24,V27,V28,I.cmd
T37|x|add Digest retry for INVITE calls and raw SIP request CLI with CSeq-scoped response matching|V27,V28,V29,I.cmd
T38|x|add redacted `--debug-sip` packet visibility for phone and raw SIP CLI|V13,V24,V25,V28,V30,I.cmd
T39|x|add SIP softphone SDP offer/answer negotiation and media CLI flags|V17,V25,V31,I.cmd
T40|x|add opt-in generic OpenAI-compatible LLM client/tests and LLM/SIP/Asterisk examples|V13,V23,V32,I.api
T41|x|clear baseline type-check diagnostics for current implementation surfaces|V33,I.ci
T42|x|add in-dialog SIP INFO DTMF support plus richer SIP CLI/Python examples|V13,V25,V30,V31,V34,I.cmd
T43|x|fix LLM env defaults for direct example execution|V32,V35,I.api
T44|x|add richer runnable LLM SIP-flow audit example|V5,V13,V32,V36,I.cmd
T45|x|fix SIP-flow audit auth redaction detection|V13,V36,V37,I.cmd
T46|x|fix Digest retry for challenged SIP softphone BYE hangup|V29,V30,V38,I.cmd
T47|x|split repo into root core `sipx` package plus `apps/*` uv workspace packages|C18,C19,V39,V40,V41,I.pkg
T48|x|rename SIP runtime and softphone public names away from `Native*` aliases|V42,I.runtime,I.pkg
T49|x|treat INVITE provisional `1xx` as progress, not no-response timeout|V43,I.runtime
T50|x|make root pytest collect only core `sipx` tests; keep app tests opt-in|C20,V44,I.pkg
T51|x|add harness runtime and SIP role ABC contracts for mock and UAC/UAS runtimes|V45,I.api,I.runtime
T52|x|fix SIP role ABC signatures so type-check accepts concrete UAC/UAS overrides|V46,I.api,I.runtime
T53|x|move Harness/Mock/Timeline/Scenario surfaces to `sipx-harness`; keep root `sipx` SIP-only|C18,C19,V39,V47,I.pkg
T54|x|rename generic public `Backend*` surfaces to `Runtime*`/`user_agent` names|C21,V48,I.api,I.runtime
T55|x|move speech protocols out of root media into `sipx-stt`/`sipx-tts` app packages|C22,V49,I.pkg
T56|x|preserve redaction line/header shape while removing secret values|V13,V50,I.api
T57|x|move generic redaction out of root `sipx` into `sipx-harness`|C18,V51,I.pkg
T58|x|move softphone ergonomics into split `SipUac`/`SipUas` modules|C23,V52,V53,I.runtime,I.api
T59|x|move SIP-only curl-like CLI into root `sipx` command surface|C24,V54,I.cmd
T60|x|add G.711 PCMU/PCMA encode/decode and synthetic silence/noise audio sources|C11,C26,V55,V60,I.api
T61|x|add RTP jitter/loss/buffer metrics snapshots|V56,V57,I.api
T62|x|add RTP jitter buffer playout with concealment and late/drop counters|V57,I.api
T63|x|add `RtpAudioSession` with send/receive, codec, synthetic media, jitter buffer, metrics|C26,V55,V56,V57,V60,I.api
T64|x|wire call-level audio modes and metrics into `SipUac`/`SipUas` calls|V52,V55,V56,V58,V59,I.api
T65|x|add CLI audio/jitter/metrics flags for `call` and `listen`|V54,V55,V56,V57,V58,I.cmd
T66|x|add optional PyAudio mode via lazy dependency path|C25,V55,I.api,I.cmd
T67|x|add configurable INVITE provisional response API for UAS|V62,V63,I.api,I.proto
T68|x|add direct root Mizu examples using generic SIP env vars, no argparse|C18,V64,I.pkg
T69|x|add core request helpers, dataclass summaries, event_hooks httpx-style dict, compact headers, capabilities, and CLI dry-run message rendering|V29,V30,V33,V58,V66,V67,V68,V69,V70,I.api,I.cmd
T70|x|add RTP wire event hooks and `debug_wire_rtp` example helper|V71,I.api

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
B9|2026-06-08|DTMF implementation added helper/softphone call path but runtime method/import was incomplete during focused validation|V34
B10|2026-06-08|`LLMChatClient.from_env()` read dataclass slot descriptors as defaults when optional env vars were missing, causing timeout float parsing failure|V35
B11|2026-06-08|SIP-flow audit treated `Authorization: [REDACTED]` as unredacted auth during deterministic security checks|V37
B12|2026-06-09|real proxy accepted authenticated INVITE but challenged in-dialog BYE; hangup path lacked Digest retry and failed with `401 Unauthorized`|V38
B13|2026-06-09|real INVITE received `183 Session Progress`, then call path reused no-response datagram timeout and failed while call was still proceeding|V43
B14|2026-06-09|SIP role ABCs used generic `**kwargs`; concrete keyword-only methods failed `uv run ty check` override validation|V46
B15|2026-06-09|softphone test imported `Timeline` from root `sipx` after harness moved to `sipx_harness`|V47
B16|2026-06-09|Asterisk package `__init__` rename left `AsteriskRuntime` outside import/export lists, causing import-time `IndentationError`|V48
B17|2026-06-09|root `sipx.media` still exported STT/TTS speech protocols after root was declared SIP/media primitive only|V49
B18|2026-06-09|`a=crypto` text redaction removed whole line marker instead of preserving safe SDP evidence shape|V50
B19|2026-06-09|generic `Redactor` stayed in root `sipx.security` after root boundary was SIP/media primitives only|V51
B20|2026-06-09|RTP stats counted duplicate payload bytes; synthetic audio `slots` omitted PRNG field|V55,V56
B21|2026-06-09|UAC/UAS split left unused imports and unformatted new role files|ruff gate; no new §V
B22|2026-06-09|PCMA silence test expected exact zero after G.711 companding; decoded silence is near-zero|V61
B23|2026-06-09|RTP UDP protocol unpacked callback `addr: object` directly, failing `uv run ty check`|V33
B24|2026-06-09|call-level RTP branch passed `audio` union including `none` into synthetic-only helper|V33
B25|2026-06-09|CLI tests monkeypatched removed `SipSoftphone` symbol after UAC/UAS migration|V53
B26|2026-06-09|T58 UAC migration left inherited async context typed as base `SipUserAgent` plus mixed test dict inference|V33
B27|2026-06-09|CLI metrics path made call fake lack `state/local_sdp/remote_sdp` fields|V58
B28|2026-06-09|example secret scan read `__pycache__` binary after importing examples|no new §V; test filter now scans text example files only
B29|2026-06-09|CLI/Mizu audio mode argparse values stayed un-narrowed, and RTP snapshot called optional session twice|V33
B30|2026-06-09|call example defaulted `SIPX_TARGET` to own demo AOR; public run got `502 Bad Gateway` plus traceback|V65
B31|2026-06-09|`smoke_tests` call branch got no final response and waited past shell timeout|V65
B32|2026-06-09|timeout regression test coroutine returned `None` where `await_call` expects `SipCall`|V33
