# sipx

`sipx` is a Python Voice/SIP workspace for call automation, IVR testing, technical softphones, contact-center workflows, real-time media validation, and AI-assisted voice applications.

The product is not a PBX wrapper, not only a SIP bot, and not a normal end-user softphone. The product is the harness: actors, scenarios, expectations, timelines, verdicts, artifacts, reports, and replayable evidence.

```text
Root sipx is SIP protocol/runtime.
The Harness lives in sipx-harness.
Asterisk is a runtime app.
SIP UAC/UAS runtime is the low-level engine.
The workspace Harness is the product.
```

## Status

This repository has an initial working harness implementation. The maintained English files in the current project structure are the implementation source of truth. `IDEA.md` is historical source material only and should not be required to implement the project.

The implementation should follow:

- `SPEC.md` for goals, constraints, invariants, public surfaces, and build tasks.
- `DESIGN.md` for detailed architecture, API, runtimes, protocol, media, softphone, Asterisk, security, testing, and roadmap decisions.
- `TODO.md` for the executable roadmap.
- `.spec/state.md` and `.spec/handoff.md` for current project state.
- `.mem/hot.md`, `.mem/decisions.md`, and `.mem/open-loops.md` for persistent project memory.

## Core Idea

`sipx` should let engineers model voice systems as executable scenarios:

```python
from sipx_harness import Harness, expect, scenario


@scenario("ivr_second_copy")
async def ivr_second_copy(h: Harness) -> None:
    caller = h.actor("caller").softphone(profile="lab")

    call = await caller.call("sip:ivr@example.com")

    await expect(call.sip).final_response(200).within(30)
    await expect(call.rtp).to_flow().within(2)
    await expect(call.media).to_hear("welcome", mode="contains").within(8)

    await call.dtmf.send("2")

    await expect(call.media).to_mean(
        "the IVR asked for the customer document number",
        confidence=0.85,
    ).within(10)

    await call.dtmf.send("12345678901#")

    await expect(call.media).to_mean(
        "the IVR confirmed the second-copy request",
        confidence=0.85,
    ).within(20)

    await call.hangup()
    await expect(call.sip).to_be_terminated_cleanly()
```

Every scenario should produce a verdict and evidence:

```text
Verdict: passed | failed | error | skipped
Artifacts: timeline.jsonl, recording.wav, transcript.json, sip.pcap, report.html
```

## Product Shape

`sipx` is three related products sharing one architecture:

| Product | Purpose |
| --- | --- |
| Voice Harness | `sipx-harness` scenario runner, `expect`, timeline, artifacts, verdicts, reports, replay. |
| Technical Softphone | SIP/RTP endpoint for engineers, automation, inspection, negative tests, and scenario recording. |
| Asterisk Integration Runtime | Asterisk call control, media, bridges, queues, recordings, and production-ish telephony workflows. |

The same scenario model should work across runtimes whenever capabilities allow it.

## Detailed Scope

The detailed implementation context that used to be spread through `IDEA.md` is now consolidated in `DESIGN.md`, `SPEC.md`, `TODO.md`, `.spec/*`, and `.mem/*`. There is intentionally no separate `docs/` tree.

`DESIGN.md` contains the expanded details for:

- Product identity and operating modes.
- API design, Python scenarios, YAML scenarios, requests-like SIP API, and transaction-level API.
- `expect` families, deterministic/temporal/probabilistic/statistical validation, verdicts, and rich failures.
- Runtime responsibility split and capability model.
- Asterisk ARI/Stasis integration, media paths, flows, config, and limitations.
- SIP/SDP/RTP/DTMF protocol scope, state machines, timers, codecs, jitter, fuzzing, and security.
- Media and AI runtime, STT/TTS app protocols, IVR, DTMF, barge-in, voice apps, and metrics.
- Technical softphone, profiles, lab hooks, scenario recorder, mixed scenarios, and UI roadmap.
- Implementation roadmap and validation gates.

## Architecture

```text
Applications / CLI / CI / QA / Softphone UI
        |
        v
sipx-harness
  Actor, Scenario, Expect, Timeline, Verdict, Artifact, Metrics
        |
        +-------------------------+-------------------------+
        |                         |                         |
        v                         v                         v
 AsteriskRuntime            SipUserAgent                Mock/Replay
 ARI, Stasis, bridges       SIP, SDP, RTP, DTMF         tests, replay
 media, recordings          strict/lab, softphone       fixtures
        |                         |
        v                         v
 Asterisk/PJSIP             SIP endpoints/PBX/SBC/IVR
```

## Main Concepts

| Concept | Meaning |
| --- | --- |
| `Harness` | `sipx_harness` runtime that owns configuration, runtimes, actors, scenario runs, and artifacts. |
| `Actor` | Programmable participant: SIP softphone, Asterisk, remote SIP target, AI bot, fake carrier, queue. |
| `Scenario` | Executable call flow with steps, fixtures, expectations, and final verdict. |
| `Call` | High-level call facade for apps and tests. |
| `CallLeg` | One leg of a call, such as a SIP dialog or Asterisk channel. |
| `Expectation` | Temporal or deterministic assertion over SIP, SDP, RTP, media, AI, Asterisk, metrics, or timeline. |
| `Timeline` | Ordered event log used for debug, replay, reports, and assertions. |
| `Verdict` | First-class outcome with reason, failures, warnings, metrics, and artifact links. |
| `Artifact` | Persisted evidence: JSONL timeline, WAV, transcript, PCAP, report. |

## Runtimes

### AsteriskRuntime

The first practical runtime should use Asterisk where Asterisk is strong:

- PJSIP endpoints and trunks.
- ARI REST commands and ARI WebSocket events.
- Dialplan `Stasis(sipx)` handoff into Python.
- Bridges, queues, recordings, MOH, DTMF, playback, transfers.
- ExternalMedia, AudioSocket, or WebSocket media for AI and STT/TTS.

This runtime is the fastest path to IVR automation, AI voice bots, contact-center flows, queue validation, and functional voice testing.

### SipUserAgent / SipUac / SipUas

The SIP user-agent runtime is required for what Asterisk intentionally hides or normalizes:

- Raw SIP wire-level assertions.
- Exact headers, CSeq, Via branch, tags, timers, retransmissions.
- Malformed SIP/SDP/RTP tests.
- Fuzzing and parser robustness.
- Technical softphone behavior.
- RTP impairment, payload validation, jitter/loss measurement.

Softphone ergonomics now live in `SipUac` and `SipUas` instead of a separate wrapper. `SipUserAgent` remains the shared transport/dialog engine; UAC and UAS own their outbound/inbound convenience behavior. Inbound UAS answers use `SipProvisionalResponse` to choose zero or more RFC 3261 `1xx` responses before the final response.

It should have two modes:

| Mode | Purpose |
| --- | --- |
| `strict` | RFC-oriented behavior for real interop and reliable softphone automation. |
| `lab` | Controlled malformed messages, protocol overrides, delayed messages, custom SDP, and fault injection. |

The SIP/SDP/RTP core should be sans-I/O so protocol logic can be tested without sockets.

## Expectations

The `expect` API should be SIP-aware and temporal. It must not copy HTTP semantics blindly.

Examples:

```python
await expect(call.sip).response(180, 183).within(5)
await expect(call.sip).final_response(200).within(30)
await expect(call.sdp).to_have_codec("PCMU")
await expect(call.rtp).packet_loss_below(1.0)
await expect(call.dtmf).to_have_sent("123#")
await expect(call.media).to_hear("enter your document number").within(10)
await expect(call.speech).to_mean("the user reached support", confidence=0.85)
```

Critical regression checks must include deterministic or temporal assertions. Semantic AI assertions are useful, but they must not be the only pass/fail signal for critical behavior.

## Timeline And Evidence

Everything important should become a timeline event:

```text
+0000ms  sip.tx        INVITE sip:ivr@example.com
+0021ms  sip.rx        100 Trying
+0310ms  sip.rx        180 Ringing
+0890ms  sip.rx        200 OK
+0892ms  sip.tx        ACK
+0940ms  rtp.rx        first packet
+1220ms  media.stt     "welcome to support"
+1230ms  expect.pass   heard "welcome"
+1400ms  dtmf.tx       "2"
+2100ms  media.stt     "enter your document number"
+2110ms  expect.pass   heard "document number"
+4000ms  sip.tx        BYE
+4020ms  sip.rx        200 OK
```

Timeline data must correlate SIP Call-ID, Asterisk channel ID, bridge ID, RTP SSRC, recording ID, transcript ID, scenario ID, actor ID, and call leg ID when available.

## MVP Roadmap

1. Document product identity and decisions.
2. Build harness core: events, timeline, verdict, artifacts, metrics.
3. Build scenario runner and `expect()` engine.
4. Build `MockRuntime` and `sipx` CLI skeleton.
5. Build `AsteriskRuntime` with ARI/Stasis.
6. Choose and implement one Asterisk media path.
7. Add media frame and barge-in policy in root; keep STT/TTS protocols in app packages.
8. Build minimum `SipUserAgent`/`SipUac`/`SipUas` runtime for technical softphone mode.
9. Add reports, replay, and scenario export.
10. Add lab mode, fuzzing, SIP/RTP conformance, and advanced interop.

## Development

Project metadata currently requires Python `>=3.14`.

Expected validation commands:

```bash
ruff format --check .
ruff check .
uv run ty check
pytest
```

Root `pytest` is intentionally core-only and collects `tests/`. App package tests under `apps/*/tests` are opt-in by explicit path when changing an app, for example:

```bash
pytest apps/cli/tests/test_cli.py
pytest apps/scenarios/tests/test_examples_templates.py
```

The repository is a `uv` workspace. `FORMAT.md` defines the `SPEC.md` format. The root package `sipx` owns SIP protocol/runtime and RTP media primitives. Harness and app packages live under `apps/*` and import the root package as a workspace dependency:

- `apps/harness`: `sipx-harness`, owns `Harness`, `Actor`, `Timeline`, `Verdict`, artifacts, profiles, reports, and mock runtimes.
- `apps/cli`: `sipx-cli`, owns the `sipx` console command.
- `apps/asterisk`: `sipx-asterisk`, owns ARI runtime and Stasis helpers.
- `apps/llm`: `sipx-llm`, owns `LLMChatClient` and LLM examples.
- `apps/scenarios`: `sipx-scenarios`, owns runnable scenario and SIP example templates.
- `apps/stt`, `apps/tts`: speech protocol/adapter packages.

Integration tests that require Asterisk must be explicitly configured and must not depend on real secrets committed to the repository.

The installed `sipx` command is SIP/RTP-only and curl-like. Top-level commands are `options`, `message`, `request`, `register`, `unregister`, `call`, and `listen`; harness `scenario`, `profile`, `replay`, and `phone` subcommands are not part of this root command surface.

Useful CLI commands:

```bash
uv run --package sipx-cli sipx register --aor sip:1001@example.com --registrar sip:pbx.example.com:5060 --username 1001 --password "$SIP_PASSWORD"
uv run --package sipx-cli sipx unregister --aor sip:1001@example.com --registrar sip:pbx.example.com:5060 --username 1001 --password "$SIP_PASSWORD"
uv run --package sipx-cli sipx call sip:6000@pbx.example.com --aor sip:1001@example.com --registrar sip:pbx.example.com --username 1001 --password "$SIP_PASSWORD" --audio noise --rtp-stats --duration 5
uv run --package sipx-cli sipx call sip:6000@pbx.example.com --aor sip:1001@example.com --registrar sip:pbx.example.com --rtp-bind 0.0.0.0 --rtp-advertise 203.0.113.10 --jitter-buffer-ms 80 --metrics-json metrics.json --debug-sip
uv run --package sipx-cli sipx listen --aor sip:1001@example.com --registrar sip:pbx.example.com --local-port 5062 --audio silence --duration 30 --rtp-stats
uv run --package sipx-cli sipx options sip:pbx.example.com --from sip:1001@example.com -i
uv run --package sipx-cli sipx message sip:1002@pbx.example.com 'hello' --from sip:1001@example.com
uv run --package sipx-cli sipx request INFO sip:1002@pbx.example.com --from sip:1001@example.com --username 1001 --password "$SIP_PASSWORD" --debug-sip -H 'Content-Type: application/dtmf-relay' -d $'Signal=1\r\nDuration=160\r\n'
uv run --package sipx-cli sipx request OPTIONS sip:pbx.example.com --from sip:1001@example.com --print-message --compact-headers --accept application/sdp --allow OPTIONS
uv run --package sipx-cli sipx call sip:6000@pbx.example.com --aor sip:1001@example.com --registrar sip:pbx.example.com --print-message --compact-headers --media-port 40000
```

Commands that need SIP account identity require explicit `--aor` and `--registrar` flags before network access. If `--remote-host` and `--remote-port` are omitted, `sipx` uses the registrar host and port.

Raw SIP request commands require `--from`/`--aor`. If `--remote-host` and `--remote-port` are omitted, `sipx` uses the target URI host and port.

When `--username` and `--password` are provided, calls and raw SIP request commands retry one `401` or `407` Digest challenge without persisting the password.

Use `--debug-sip` to print redacted SIP datagrams to stderr as they are sent and received. `Authorization` and `Proxy-Authorization` lines are redacted before printing.

Use `--print-message` to render a SIP request without opening a socket. Use `--compact-headers` to serialize RFC compact header names where defined; receive parsing always expands compact names to canonical headers. Raw request commands also accept explicit capability headers with repeatable `--accept`, `--allow`, `--allow-event`, and `--supported`. The CLI does not claim unsupported `Allow` or event-package features unless you set them.

Outbound `SipUac` calls send an SDP audio offer by default, open RTP while the call exists, and validate the `2xx` SDP answer before reporting the call as confirmed. Use `--rtp-bind` for the local RTP socket, `--rtp-advertise` for the SDP address, `--media-port`/`--rtp-port` for the RTP port, and repeatable `--codec` to adjust offered media. Use `--dtmf` to send in-dialog SIP INFO DTMF after confirmation.

Current RTP media primitives include PCMU/PCMA encode/decode without `audioop`, deterministic synthetic `silence` and `noise` PCM sources, RFC3550-style jitter metrics, tx/rx packet metrics, a fixed target/max `RtpJitterBuffer` with concealment and late/drop counters, and `RtpAudioSession` for UDP RTP send/receive with metrics snapshots. High-level `SipUac.call(audio="none|silence|noise|pyaudio")` and `SipUas.answer(audio="none|silence|noise|pyaudio")` support no-device synthetic media plus optional lazy PyAudio microphone input. The CLI exposes `--audio`, `--jitter-buffer-ms`, `--rtp-stats`, and `--metrics-json` on `call` and `listen`.

UAS provisional response examples:

```python
from sipx import SipProvisionalResponse, SipUas

uas = SipUas(aor="sip:1001@example.com")

# Default: 180 Ringing, then 200 OK.
await uas.answer()

# RFC-valid direct final response: INVITE -> 200 OK -> ACK.
await uas.answer(provisionals=())

# Explicit carrier-style progress: 100 Trying, 183 Session Progress with SDP, 200 OK.
await uas.answer(
    provisionals=(
        SipProvisionalResponse.trying(),
        SipProvisionalResponse.session_progress(include_sdp=True),
    )
)
```

Hooks mutate SIP traffic only in `lab` mode. Handlers observe traffic and can be registered as decorators:

```python
from sipx import SipHandlers, SipHooks, SipMessage, SipRequest

hooks = SipHooks()

@hooks.before_send_message
def add_header(message: SipMessage, remote: tuple[str, int]) -> SipMessage:
    if isinstance(message, SipRequest):
        message.headers.add("X-Lab", "yes")
    return message

handlers = SipHandlers()

@handlers.on_response
def record_response(response, remote):
    print(response.summary())
```

Summaries are dataclasses. Convert them to JSON at the CLI/example edge with `dataclasses.asdict()` or a JSON helper:

```python
from dataclasses import asdict

summary = response.summary()
payload = asdict(summary)
```

## Examples

Use `uv run` from the repository root so the local package is importable.

SIP operation examples live under `apps/scenarios/examples/sip`:

```bash
uv run --package sipx-cli sipx register --aor sip:1001@example.com --registrar sip:pbx.example.com --username 1001 --password "$SIP_PASSWORD" --debug-sip --keepalive 10
uv run --package sipx-cli sipx options sip:pbx.example.com --from sip:1001@example.com --include --debug-sip
uv run --package sipx-cli sipx message sip:1002@example.com 'hello from sipx' --from sip:1001@example.com --debug-sip
uv run --package sipx-cli sipx call sip:ivr@example.com --aor sip:1001@example.com --registrar sip:pbx.example.com --codec PCMU --audio noise --rtp-stats --dtmf '123#' --duration 3 --debug-sip
uv run --package sipx-cli sipx request INFO sip:ivr@example.com --from sip:1001@example.com -H 'Content-Type: application/dtmf-relay' -d $'Signal=1\r\nDuration=160\r\n' --include --debug-sip
```

Python templates:

```python
from apps.scenarios.examples.sip.call_with_dtmf import call_with_dtmf

call_id = await call_with_dtmf("sip:ivr@example.com", digits="123#")
```

More command examples are in `apps/scenarios/examples/sip/README.md`. `apps/scenarios/examples/sip/sip_cli_flow.py` builds reusable command arrays for register, OPTIONS, MESSAGE, raw INFO DTMF, and call-with-DTMF flows.

Runnable example files:

```bash
uv run --package sipx-scenarios python apps/scenarios/examples/sip/sip_cli_flow.py

SIPX_AOR=sip:1001@example.com \
SIPX_REGISTRAR=sip:pbx.example.com \
SIPX_USERNAME=1001 \
SIPX_PASSWORD=... \
uv run --package sipx-scenarios python apps/scenarios/examples/sip/call_with_dtmf.py sip:ivr@example.com --digits '123#'

export SIPX_LOCAL_HOST=<your-local-ip>
export SIPX_TARGET=sip:<target>@demo.mizu-voip.com:37075
uv run python -m sipx.examples.register
SIPX_AUDIO=noise uv run python -m sipx.examples.metrics
```

LLM scenario files are run directly for now:

```bash
uv run --package sipx-llm python apps/llm/examples/semantic_smoke.py
uv run --package sipx-llm python apps/llm/examples/sip_flow_audit.py
uv run --package sipx-llm python apps/llm/examples/sip_flow_audit.py --trace-file /path/to/sip-trace.txt
```

Direct SIP example scripts live under `sipx.examples`. They default to the public Mizu demo account, but use generic SIP env vars so the same code can target another SIP provider:

```bash
export SIPX_LOCAL_HOST=<your-local-ip>
export SIPX_TARGET=sip:<target>@demo.mizu-voip.com:37075

# Optional overrides for non-Mizu providers:
export SIPX_AOR=sip:1001@example.com
export SIPX_REGISTRAR=sip:pbx.example.com:5060
export SIPX_USERNAME=1001
export SIPX_PASSWORD=...
export SIPX_REMOTE_HOST=pbx.example.com
export SIPX_REMOTE_PORT=5060

uv run python -m sipx.examples.register
uv run python -m sipx.examples.options
uv run python -m sipx.examples.build_request
uv run python -m sipx.examples.handlers
uv run python -m sipx.examples.invite_without_sdp
SIPX_AUDIO=silence uv run python -m sipx.examples.invite_with_sdp
SIPX_AUDIO=noise uv run python -m sipx.examples.metrics
SIPX_AUDIO=noise uv run python -m sipx.examples.manipulation
SIPX_RUN_CALL=1 uv run python -m sipx.examples.smoke_tests
```

Call examples require `SIPX_TARGET`; without it they print a structured JSON configuration error instead of opening a network call to the demo account itself.

LLM examples use a generic OpenAI-compatible `/chat/completions` provider and read provider settings only from runtime environment variables:

```bash
export SIPX_LLM_API_KEY=...
export SIPX_LLM_BASE_URL=https://api.openai.com/v1
export SIPX_LLM_MODEL=gpt-4o-mini
uv run --package sipx-llm python apps/llm/examples/sip_flow_audit.py --trace-file /path/to/sip-trace.txt
```

`semantic_smoke.py` is the quick smoke test. `sip_flow_audit.py` is the richer example: it extracts deterministic SIP signals, asks the LLM for structured JSON, returns summary, behavior, risk score, protocol findings, media assessment, and next actions.

Templates live under `apps/llm/examples`, `apps/asterisk/examples`, and `apps/scenarios/examples`. The live LLM smoke test is skipped unless `SIPX_LLM_API_KEY` is set.

GitHub automation lives under `.github/workflows`:

- `ci.yml` runs uv sync, workspace CLI smoke test, ruff, ty, pytest, and workspace package build.
- `asterisk.yml` starts the local Docker Asterisk lab and runs opt-in integration tests.
- `create-release.yml` creates a draft `v<pyproject version>` release on `master`.
- `release.yml` verifies the release tag, tests, builds, and publishes to PyPI via trusted publishing.

## Asterisk Lab

The repo includes a local Asterisk 22 lab under `docker/asterisk` for Asterisk runtime and SIP UAC/UAS integration work.

```bash
docker compose -f docker/asterisk/docker-compose.yml up --build
SIPX_ASTERISK_INTEGRATION=1 python -m pytest apps/asterisk/tests/test_asterisk_integration.py
```

Default lab-only endpoints:

- ARI: `http://127.0.0.1:8088/ari`, user `sipx`, password `sipx`.
- SIP UDP: `127.0.0.1:5060`.
- SIP UAS tests: `sip:1000@127.0.0.1:5060` and `sip:1001@127.0.0.1:5060`.

## Security Notes

- Treat recordings and transcripts as sensitive.
- Redact SIP auth headers, ARI credentials, provider tokens, SDP crypto lines, and configured PII before logs/artifacts.
- Keep Python as a separate process from Asterisk loadable modules unless licensing and maintenance tradeoffs are explicitly accepted.
- Use allowlists, CPS limits, consent, and opt-out controls before real outbound calling.
- Prefer TLS/WSS for ARI and media WebSockets in production.
