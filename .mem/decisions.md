# Decisions

| id | date | decision | reason |
| --- | --- | --- | --- |
| D1 | 2026-06-08 | Product = Voice/SIP Harness, not just UserAgent/bot. | Scenarios, expectations, evidence, and timeline are the differentiator. |
| D2 | 2026-06-08 | Asterisk = runtime/app, not conceptual core. | Asterisk accelerates PBX/media/interop but hides wire-level SIP details. |
| D3 | 2026-06-08 | MVP starts Asterisk-backed. | Delivers IVR, bot, queue, recording, trunks, and media faster. |
| D4 | 2026-06-08 | SIP UAC/UAS runtime remains required. | Needed for technical softphone, raw SIP/SDP/RTP validation, lab mode, fuzzing. |
| D5 | 2026-06-08 | Harness API centers on Harness, Actor, Scenario, Expect, Timeline, Verdict, Artifact. | Keeps scenarios portable across runtimes. |
| D6 | 2026-06-08 | Runtimes declare capabilities. | Prevents false claims like raw SIP assertions on Asterisk-only data. |
| D7 | 2026-06-08 | Deterministic assertions first; semantic AI assertions supplemental. | AI output is probabilistic and unsuitable as sole critical regression gate. |
| D8 | 2026-06-08 | SIP protocol core should be sans-I/O. | Enables unit tests, fuzzing, fake transports, and deterministic protocol behavior. |
| D9 | 2026-06-08 | Python process stays separate from Asterisk modules. | Reduces GPL/loadable-module and maintenance risk. |
| D10 | 2026-06-08 | Use Python `>=3.14` unless project requirement changes. | Current `pyproject.toml` requires it. |
| D11 | 2026-06-08 | Public package/import name is `sipx`. | User explicitly selected `sipx`; `pyproject.toml` already matches. |
| D12 | 2026-06-08 | CLI command name is `sipx`. | Keeps command aligned with package/project identity. |
| D13 | 2026-06-08 | Technical softphone uses `SipUserAgent`/`SipUac`/`SipUas`. | Final `IDEA.md` direction: Asterisk is runtime/peer/resource, not softphone foundation. |
| D14 | 2026-06-08 | Technical softphone is headless engine first. | CLI/TUI/GUI should be clients of the same engine, not separate products. |
| D15 | 2026-06-08 | PJSIP/PJSUA2 is optional future runtime. | Useful for robust softphone interop, but weaker for malformed/wire-level lab control. |
| D16 | 2026-06-08 | Mixed SIP/Asterisk scenarios are required. | Final architecture needs SIP actors, Asterisk actors, and remote targets in one timeline. |
| D17 | 2026-06-08 | Maintained English files in current structure replace `IDEA.md` for implementation context. | User wants no dependency on `IDEA.md` and no separate `/docs`; all implementation details must be explicit in `README.md`, `SPEC.md`, `DESIGN.md`, `TODO.md`, `.spec/*`, and `.mem/*`. |
| D18 | 2026-06-08 | Implementation proceeds in small committed blocks with version, changelog, TODO, spec state, and memory updates every time. | User explicitly requested this pipeline so other agents follow the same flow. |
| D19 | 2026-06-08 | Initial tests avoid `pytest-asyncio` markers and use `asyncio.run`. | Active `pytest` did not load the async plugin; plain pytest compatibility keeps validation runnable. |
| D20 | 2026-06-08 | `Harness()` defaults to `MockRuntime`. | Enables no-network unit tests and CLI skeleton before Asterisk or SIP runtimes exist. |
| D21 | 2026-06-08 | Artifact writes use default central redaction. | Secret redaction must be automatic before logs/transcripts/recordings grow. |
| D22 | 2026-06-08 | Media layer starts with protocols and value objects, not provider adapters. | Keeps STT/TTS/LLM providers out of the media clock and avoids premature dependency choices. |
| D23 | 2026-06-08 | SIP runtime starts with sans-I/O parse/serialize primitives. | Keeps protocol correctness testable before sockets, timers, transactions, or async runtime. |
| D24 | 2026-06-08 | SDP starts with audio-only PCMU/PCMA plus `telephone-event`. | Matches MVP codec/DTMF scope without adding premature video or advanced media negotiation. |
| D25 | 2026-06-08 | RTP/DTMF starts sans-I/O before media runtime. | Packet correctness and RFC4733 event behavior should be deterministic before sockets/jitter/audio clocks. |
| D26 | 2026-06-08 | SIP transactions/dialogs start sans-I/O and partial. | T21 is broad; client INVITE and dialog state should be verified before adding UAS, REGISTER, auth, sockets, and timers. |
| D27 | 2026-06-08 | SIP Digest helper implements protocol MD5 only. | SIP Digest requires MD5 response generation; code uses `usedforsecurity=False` and does not store secrets. |
| D28 | 2026-06-08 | Continue T21 as small sans-I/O sub-blocks before SIP runtime. | Dialog, transaction, auth, and request correctness are easier to validate before sockets/timers and strict runtime integration. |
| D29 | 2026-06-08 | REGISTER client flow accepts password only at auth retry generation time. | Keeps Digest response generation possible without storing secrets in flow state. |
| D30 | 2026-06-08 | `SipUserAgent` uses real UDP sockets for SIP wire runtime. | Technical softphone and raw SIP validation need real transport behavior; loopback tests validate without external infrastructure. |
| D31 | 2026-06-08 | SIP strict call runtime starts with SIP signaling before media. | T21 is signaling-focused; SDP/RTP media wiring can build on confirmed dialog/call state later. |
| D32 | 2026-06-08 | CANCEL runtime models pending INVITE separately from confirmed calls. | CANCEL terminates an INVITE transaction before dialog confirmation, so it should not reuse `SipCall`. |
| D33 | 2026-06-08 | SIP REGISTER orchestration reuses `RegisterClientFlow` and only accepts password at retry time. | Keeps UDP runtime aligned with no-password-storage Digest decision. |
| D34 | 2026-06-08 | SIP retransmission timers are configurable policy objects. | Tests can run fast while strict runtime keeps real async timer behavior. |
| D35 | 2026-06-08 | Asterisk ARI control plane starts dependency-free with injectable transports. | Stdlib HTTP plus local WebSocket text-frame reader keeps first T9 block testable without syncing new runtime dependencies or requiring real Asterisk. |
| D36 | 2026-06-08 | Asterisk control method mapping remains at ARI resource level first. | T10 needs timeline evidence for channels/bridges/playback/hangup/DTMF before higher-level call facades and media port decisions. |
| D37 | 2026-06-08 | WebSocket media is the Asterisk MVP media path. | Best project-wide tradeoff: simpler bidirectional media and flow control now, while preserving AudioSocket and ExternalMedia RTP as later paths. |
| D38 | 2026-06-08 | Inbound Stasis example lives with the Asterisk app package. | Current structure remains source of truth while keeping the example executable and testable without real Asterisk. |
| D39 | 2026-06-08 | SIP technical softphone starts as a headless engine wrapper over `SipUserAgent`. | T22 needs programmable register/call/answer behavior now; CLI/TUI/GUI and profile loading remain later clients/features. |
| D40 | 2026-06-08 | SIP protocol manipulation uses lab-only `SipHooks`. | Keeps strict mode RFC-oriented while giving technical softphones and protocol tests controlled hooks for headers, SDP, timers, malformed bytes, and received events. |
| D41 | 2026-06-08 | Asterisk integration tests are opt-in behind `SIPX_ASTERISK_INTEGRATION=1`. | Normal CI must stay no-secret/no-Docker; local lab can still validate ARI and SIP UAC/UAS against Asterisk. |
| D42 | 2026-06-08 | `PjsipRuntime` remains optional future runtime after SIP lab and Asterisk paths. | PJSIP is better for robust endpoint interop but worse for malformed wire-level control than `SipUserAgent`. |
| D43 | 2026-06-08 | Use hatchling build metadata for package-manager CLI execution. | `uv run sipx` needs an installable project so the configured console script wins over direct local package execution. |
| D44 | 2026-06-08 | Operational CLI stays on stdlib `argparse` for now. | Avoids new runtime dependencies while exposing SIP/profile behavior. |
| D45 | 2026-06-08 | GitHub workflows read version from `pyproject.toml`. | The new project uses hatchling metadata and has no old `sipx/_version.py`. |
| D46 | 2026-06-08 | Phone CLI must not use silent localhost network defaults. | Missing account/registrar input should be a local UX error, not a SIP timeout. |
| D47 | 2026-06-08 | Raw SIP CLI uses `SipUserAgent` directly. | OPTIONS, MESSAGE, and generic request behavior should share the SIP wire path without adding new runtime dependencies. |
| D48 | 2026-06-08 | Digest auth retries are one-shot for now. | Avoids infinite auth loops while supporting real proxy `401/407` challenges. |
| D49 | 2026-06-08 | CLI packet debug uses a strict-mode wire event callback, not lab hooks. | Users need to inspect real interop traffic without enabling mutation/fault-injection mode. |
| D50 | 2026-06-08 | SIP softphone offers audio SDP by default on outbound calls. | Real SIP providers commonly reject authenticated INVITEs that do not advertise media. |
| D51 | 2026-06-08 | LLM provider keys are runtime environment input only. | Keeps examples/tests useful without persisting user-supplied API keys. |
| D52 | 2026-06-08 | Use `uv run ty check` as the type-check validation gate. | `ty` is available through the project dev environment even though the system interpreter lacks `python -m ty`. |
| D53 | 2026-06-08 | LLM client is generic OpenAI-compatible, not provider-named. | Lets users point templates at OpenAI-compatible APIs without renaming code per vendor. |
| D54 | 2026-06-08 | CLI DTMF starts with SIP INFO for confirmed SIP calls. | It is minimal, testable, and useful before full RTP RFC4733 media send is implemented. |
| D55 | 2026-06-09 | In-dialog BYE Digest retry follows the same one-shot policy as INVITE auth retry. | Real proxies can challenge hangup too; one retry fixes interop without risking infinite auth loops or storing passwords. |
| D56 | 2026-06-09 | Root package `sipx` is core-only; app surfaces move to `apps/*` workspace packages. | Keeps protocol/harness core importable without CLI, LLM, Asterisk, or softphone app coupling. |
| D57 | 2026-06-09 | Console command `sipx` belongs to workspace package `sipx-cli`. | The CLI composes app packages while root `sipx` remains a reusable library. |
| D58 | 2026-06-09 | Public runtime names use SIP/UAC/UAS terms, not `Native*`. | User rejected alias-based cleanup; real class/import names should be `SipUserAgent`, `SipUac`, and `SipUas`. |
| D59 | 2026-06-09 | INVITE `timeout` means no matching SIP response before first provisional/final response. | `183 Session Progress` proves signaling is active; proceeding calls should wait for final response or caller cancellation, not fail as no datagram received. |
| D60 | 2026-06-09 | Root `pytest` covers only core `sipx` tests. | Apps are workspace packages; app tests stay opt-in by explicit path/package when app code changes. |
| D61 | 2026-06-09 | Keep `MockRuntime` as harness deterministic test-double and put contracts in ABCs. | Removing it would make `Harness()` and scenario tests need network/app packages; ABCs give clearer boundaries without pretending mock is production SIP. |
| D62 | 2026-06-09 | Model SIP UAC/UAS as runtime ABC roles. | `SipUserAgent` can implement wire/UAC/UAS behavior while `SipUac`/`SipUas` expose clearer role names for tests/apps. |
| D63 | 2026-06-09 | SIP runtime ABC method signatures stay explicit, not `**kwargs` catch-alls. | Type-check validates overrides and catches drift between contracts and concrete UAC/UAS methods. |
| D64 | 2026-06-09 | Root `sipx` is SIP-only; harness surfaces live in `sipx_harness`. | Keeps root import free of Harness/Mock/Timeline/Scenario and app dependencies. |
| D65 | 2026-06-09 | Public names use `runtime`/`user_agent`, not generic `backend`. | User rejected aliases and generic backend wording; names should reflect actual role. |
| D66 | 2026-06-09 | STT/TTS protocols live in `sipx_stt`/`sipx_tts`, not root `sipx.media`. | Root media should stay generic audio primitives and avoid app/provider surfaces. |
| D67 | 2026-06-09 | Generic redaction lives in `sipx_harness`, not root `sipx.security`. | Redaction is harness/artifact/app concern; root should stay SIP/media primitives and SIP runtime. |
| D68 | 2026-06-09 | Softphone ergonomics move into high-level `SipUac`/`SipUas`, not a separate `SipSoftphone` package. | User wants UAC and UAS to own their particular outbound/inbound behavior instead of a redundant wrapper. |
| D69 | 2026-06-09 | Root CLI should become SIP/RTP-only and curl/httpx-cli-like. | User wants `sipx` to control SIP directly with explicit flags, not mix harness/scenario/profile UX into the main command. |
| D70 | 2026-06-09 | RTP media needs jitter buffer and metrics before PyAudio. | Audio correctness requires playout smoothing and observability, not only UDP send/receive. |
| D71 | 2026-06-09 | Synthetic `silence`/`noise` audio modes are first-class. | Users need RTP that symbolizes audio and keeps media path alive without opening a microphone/speaker. |
| D72 | 2026-06-09 | Remove `sipx-softphone` / `sipx_softphone` from workspace. | Public SIP phone ergonomics belong in root `SipUac`/`SipUas`; examples belong in `apps/scenarios/examples`. |
| D73 | 2026-06-09 | Root `sipx` CLI is SIP/RTP-only. | Keeps the console command curl-like and prevents harness scenario/profile/replay UX from leaking into the root SIP tool. |
| D74 | 2026-06-09 | PyAudio is optional and lazy. | Root installs should stay native-free by default while still supporting microphone RTP when users install PyAudio themselves. |
| D75 | 2026-06-09 | Break old single-provisional UAS API in favor of `provisionals`. | No users depend on old params; `provisionals=None|()|(...)` is simpler, Pythonic, and closer to RFC 3261 `0+` provisional responses. |
| D76 | 2026-06-09 | Direct SIP examples may live under `sipx.examples`. | Root examples use only SIP root APIs and env vars, while harness/app examples stay outside root package. |
| D77 | 2026-06-09 | Root call examples require explicit `SIPX_TARGET` and bounded waits. | Public demo has no safe universal call target; examples should not call own AOR by default or hang after provisional-only behavior. |
| D78 | 2026-06-09 | Use `event_hooks` httpx-style dict without compatibility aliases. | httpx pattern is simpler, well-known, and side-effect only. `SipHooks`/`SipHandlers` decorator APIs removed. |
| D79 | 2026-06-09 | Summaries stay dataclasses; JSON conversion happens at CLI/example edge. | Keeps core Python API typed while preserving structured output for command-line users. |
| D80 | 2026-06-09 | Compact headers and advertised capabilities are explicit opt-ins. | Avoids changing default canonical wire output or claiming unsupported SIP features. |
| D81 | 2026-06-12 | Legacy API removed entirely in `3.0.0`; `AsyncClient` is the only client runtime. | User direction "nao precisa de nada legacy"; one client surface eliminates duplicate runtimes, stale exports, and migration debt. |
| D82 | 2026-06-12 | CLI drops `call`/`listen` RTP softphone commands until `AsyncClient` gains media orchestration. | `AsyncClient` has no SDP/RTP session path; keeping the commands would require keeping the legacy runtime. |
| D83 | 2026-06-12 | `AsyncClient` gains generic `request()` and in-dialog `ack()`/`bye()` from `Dialog` state. | Restores curl-like escape hatch and proper INVITE dialog teardown without the legacy engine. |
| D84 | 2026-06-13 | UAC calls return the first final `Response`; intermediate `1xx`/`401`/`407` responses live on `response.history` (httpx-style), each with its `.request`. | User asked whether `request`/`options` return all transactions/responses; one final return stays simple while `history` exposes the full exchange without forcing event hooks. |
