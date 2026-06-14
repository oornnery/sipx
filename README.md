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

`sipx` aims to let engineers model voice systems as executable scenarios. The
scenario API below is the **planned harness design** (to be provided by
`sipx-harness`), not an API implemented by the core `sipx` package today:

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
 AsteriskRuntime            AsyncClient                 Mock/Replay
 ARI, Stasis, bridges       SIP, SDP, RTP, DTMF         tests, replay
 media, recordings          UAC/UAS, transports         fixtures
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

### AsyncClient

The SIP client runtime is required for what Asterisk intentionally hides or normalizes:

- Raw SIP wire-level assertions.
- Exact headers, CSeq, Via branch, and tags.
- Malformed SIP/SDP/RTP tests.
- Fuzzing and parser robustness.
- RTP impairment, payload validation, jitter/loss measurement.

`AsyncClient` is an httpx-style async SIP client. UAC methods (`invite`, `register`, `message`, `options`, `subscribe`, generic `request`, in-dialog `ack`/`bye`, and `cancel`) and UAS handler decorators (`on_invite`, `on_message`, `on_options`, `on_subscribe`) share one client, one `ClientConfig`, event hooks (`request`, `response`, `provisional`), and a generator-based Digest `AuthFlow`.

Every UAC call returns one final `Response` (the first `>= 200` reply). Intermediate responses — provisional `1xx` and `401`/`407` Digest challenges — are collected on `response.history` in arrival order, each carrying its own `.request`, so the full request/response exchange is recoverable from a single call. Live streaming of each event is still available through `event_hooks`.

The SIP/SDP/RTP core should be sans-I/O so protocol logic can be tested without sockets.

#### AsyncClient status and RFC limitations

`AsyncClient` is a UAC/UAS runtime. It sends a request, correlates the reply,
and runs the Digest `AuthFlow`, which is enough for REGISTER, OPTIONS, MESSAGE,
INVITE/ACK/BYE, SUBSCRIBE, and arbitrary `request()` calls against a cooperative
peer. The P0/P1/P2 security and RFC hardening roadmap is complete:

- **Retransmission and §17 timers (since 3.5.0).** On UDP, requests are
  retransmitted starting at T1 and doubling (capped at T2 for non-INVITE) until
  a reply arrives or `ClientConfig.timeout` elapses; INVITE stops retransmitting
  after the first provisional; TCP/TLS never retransmit. Toggle with
  `ClientConfig.retransmit`.
- **INVITE error ACK and CANCEL (since 3.4.0).** Non-2xx INVITE finals are
  auto-ACKed on the INVITE branch (§17.1.1.3); `cancel(call_id)` cancels a
  pending INVITE (§9) from a concurrent task; `ack(call_id)` still sends the
  in-dialog 2xx ACK.
- **rport / learned address (since 3.4.0).** Outgoing UDP Via carries `;rport`
  (RFC 3581, toggle `ClientConfig.rport`); the public `(host, port)` learned
  from `received`/`rport` is exposed as `AsyncClient.learned_address`.
- **PRACK / 100rel (since 3.6.0).** Reliable provisionals (RSeq + `100rel`) are
  auto-PRACKed in the early dialog with a `RAck` header (RFC 3262).
- **Strict response correlation (since 3.2.0; hostname fix in 3.7.0).** Replies
  must match `Call-ID`, CSeq number/method, top Via `branch`, and the request
  destination port. The source host is enforced only when the target is an IP
  literal; hostname targets accept the reply from the resolved IP (so peers
  addressed by name, like the public Mizu demo, no longer time out). Forged
  datagrams with a matching `Call-ID` but wrong branch are dropped.
- **Digest MD5 and SHA-256 (since 3.6.0).** `AuthFlow` supports `MD5`,
  `MD5-sess`, `SHA-256`, and `SHA-256-sess` (RFC 7616/8760); single challenge,
  fixed nonce-count.
- **Dialog tag matching (since 3.6.0).** UAC `Dialog.update` rejects responses
  whose From/To tags conflict with the dialog (§12.2.2); UAS dialogs stay
  Call-ID-matched.
- **Content-Length on every outbound request (since 3.2.0).** ``Request.to_bytes()``
  adds ``Content-Length`` when absent, which matters for TCP/TLS framing.
- **Inbound requests are not auto-routed.** The receive loop dispatches
  responses to in-flight calls; deliver inbound requests to `handle_request`
  yourself to reach the `on_*` UAS handlers.

Standalone extension handlers under `sipx/extensions/` (PRACK, DNS, events,
presence, outbound) remain test-only and are not wired into the client path.

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
8. Build minimum `AsyncClient` runtime for technical SIP automation.
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
pytest apps/fastapi/tests/test_app.py
pytest apps/scenarios/tests/test_examples_templates.py
```

The repository is a `uv` workspace. `FORMAT.md` defines the `SPEC.md` format. The root package `sipx` owns SIP protocol/runtime and RTP media primitives. Harness and app packages live under `apps/*` and import the root package as a workspace dependency:

- `apps/harness`: `sipx-harness`, owns `Harness`, `Actor`, `Timeline`, `Verdict`, artifacts, profiles, reports, and mock runtimes.
- `apps/cli`: `sipx-cli`, owns the `sipx` console command.
- `apps/fastapi`: `sipx-fastapi`, REST service demonstrating `AsyncClient` lifespan wiring (OPTIONS, REGISTER, MESSAGE, INVITE, CANCEL, generic SIP).
- `apps/asterisk`: `sipx-asterisk`, owns ARI runtime and Stasis helpers.
- `apps/llm`: `sipx-llm`, owns `LLMChatClient` and LLM examples.
- `apps/scenarios`: `sipx-scenarios`, owns runnable scenario and SIP example templates.
- `apps/stt`, `apps/tts`: speech protocol/adapter packages.

Integration tests that require Asterisk must be explicitly configured and must not depend on real secrets committed to the repository.

A curl-like `sipx` console command built on `AsyncClient` lives in the `apps/cli`
(`sipx-cli`) app; see `apps/cli/README.md`. The examples in this README use only
the base `sipx` package.

Current RTP media primitives include PCMU/PCMA encode/decode without `audioop`, deterministic synthetic `silence` and `noise` PCM sources, RFC3550-style jitter metrics, tx/rx packet metrics, a fixed target/max `RtpJitterBuffer` with concealment and late/drop counters, and `RtpAudioSession` for UDP RTP send/receive with metrics snapshots.

AsyncClient usage examples:

```python
from sipx import AsyncClient, AuthFlow, ClientConfig

# rport (RFC 3581) and §17 retransmission are on by default; toggle if needed.
config = ClientConfig(
    from_uri="sip:1001@example.com",
    timeout=5.0,
    rport=True,
    retransmit=True,
)
auth = AuthFlow(username="1001", password="secret")

async with AsyncClient(config=config, auth=auth) as client:
    response = await client.register("sip:pbx.example.com")
    # Intermediate 1xx and 401/407 challenges are kept on response.history:
    challenge_codes = [r.status_code for r in response.history]

    response = await client.options("sip:pbx.example.com")
    response = await client.message("sip:1002@example.com", "hello")

    response = await client.invite("sip:6000@pbx.example.com")
    call_id = response.headers["Call-ID"]
    await client.ack(call_id)
    await client.bye(call_id)
```

`invite()` blocks until the final response, so to CANCEL a still-ringing call
(RFC 3261 §9) run the INVITE in one task and cancel it from another. Set an
explicit `Call-ID` so the second task knows what to target:

```python
import asyncio

async with AsyncClient(config=config, auth=auth) as client:
    call_id = "demo-call-1"
    invite = asyncio.create_task(
        client.invite("sip:6000@pbx.example.com", **{"Call-ID": call_id})
    )
    await asyncio.sleep(1)
    await client.cancel(call_id)   # 200 OK to the CANCEL
    response = await invite        # 487 Request Terminated for the INVITE
```

Event hooks follow the httpx pattern: a dict mapping event names (`request`, `response`, `provisional`) to lists of sync or async callables. All hooks are side-effect only (return value is ignored):

```python
def log_request(request) -> None:
    print(f"> {request.method} {request.uri}")

def log_response(response) -> None:
    print(f"< {response.status_code}")

client = AsyncClient(
    event_hooks={"request": [log_request], "response": [log_response]},
)
```

An `AsyncClient` response exposes `status_code`, `reason`, `headers`, `body`, and
`history` directly. Convert what you need to JSON at the CLI/example edge:

```python
payload = {
    "status_code": response.status_code,
    "reason": response.reason,
    "headers": dict(response.headers),
    "history": [r.status_code for r in response.history],
}
```

## Examples

Runnable example scripts live under `sipx.examples` and use only the base `sipx`
package (the `AsyncClient` API) — no app packages required. Run them with
`uv run` from the repository root so the local package is importable. They
default to the public Mizu demo account but read generic `SIPX_*` env vars, so
the same code can target any SIP provider:

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
uv run python -m sipx.examples.unregister
uv run python -m sipx.examples.options
uv run python -m sipx.examples.message
uv run python -m sipx.examples.subscribe
uv run python -m sipx.examples.invite
uv run python -m sipx.examples.call
uv run python -m sipx.examples.cancel
uv run python -m sipx.examples.info_dtmf
uv run python -m sipx.examples.hooks_history
uv run python -m sipx.examples.server
```

Set `SIPX_DEBUG=1` to print the SIP request/response wire to stderr, for example
`SIPX_DEBUG=1 uv run python -m sipx.examples.invite`.

The `register`, `unregister`, `options`, `message`, `subscribe`, `invite`,
`call`, `cancel`, `info_dtmf`, and `hooks_history` examples talk to a live SIP
peer (default: the public Mizu demo account). `cancel` starts an INVITE and
aborts it from a second task (RFC 3261 §9). `server` is offline: it registers
UAS handlers and feeds them synthetic requests via `handle_request` to show
response shaping.

Extra per-example env vars: `SIPX_EXPIRES` (register), `SIPX_MESSAGE` /
`SIPX_CONTENT_TYPE` (message), `SIPX_EVENT` / `SIPX_ACCEPT` (subscribe),
`SIPX_CODECS` / `SIPX_RTP_PORT` (call), and `SIPX_CANCEL_AFTER` (cancel).

Apps built on top of `sipx` (CLI, FastAPI, Asterisk, LLM, scenarios) live under
`apps/*` and ship their own READMEs and examples; those are intentionally out of
scope for this section.

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
