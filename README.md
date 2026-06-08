# sipx

`sipx` is a Python programmable Voice/SIP Harness for call automation, IVR testing, technical softphones, contact-center workflows, real-time media validation, and AI-assisted voice applications.

The product is not a PBX wrapper, not only a SIP bot, and not a normal end-user softphone. The product is the harness: actors, scenarios, expectations, timelines, verdicts, artifacts, reports, and replayable evidence.

```text
Asterisk is a backend.
Native SIP is the low-level engine.
The Harness is the product.
```

## Status

This repository has an initial working harness implementation. The maintained English files in the current project structure are the implementation source of truth. `IDEA.md` is historical source material only and should not be required to implement the project.

The implementation should follow:

- `SPEC.md` for goals, constraints, invariants, public surfaces, and build tasks.
- `DESIGN.md` for detailed architecture, API, backends, protocol, media, softphone, Asterisk, security, testing, and roadmap decisions.
- `TODO.md` for the executable roadmap.
- `.spec/state.md` and `.spec/handoff.md` for current project state.
- `.mem/hot.md`, `.mem/decisions.md`, and `.mem/open-loops.md` for persistent project memory.

## Core Idea

`sipx` should let engineers model voice systems as executable scenarios:

```python
from sipx import Harness, expect, scenario


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
| Voice Harness | Core scenario runner, `expect`, timeline, artifacts, verdicts, reports, replay. |
| Technical Softphone | Native SIP/RTP endpoint for engineers, automation, inspection, negative tests, and scenario recording. |
| Asterisk Integration Backend | Asterisk-backed call control, media, bridges, queues, recordings, and production-ish telephony workflows. |

The same scenario model should work across backends whenever capabilities allow it.

## Detailed Scope

The detailed implementation context that used to be spread through `IDEA.md` is now consolidated in `DESIGN.md`, `SPEC.md`, `TODO.md`, `.spec/*`, and `.mem/*`. There is intentionally no separate `docs/` tree.

`DESIGN.md` contains the expanded details for:

- Product identity and operating modes.
- API design, Python scenarios, YAML scenarios, requests-like SIP API, and transaction-level API.
- `expect` families, deterministic/temporal/probabilistic/statistical validation, verdicts, and rich failures.
- Backend responsibility split and capability model.
- Asterisk ARI/Stasis integration, media paths, flows, config, and limitations.
- Native SIP/SDP/RTP/DTMF protocol scope, state machines, timers, codecs, jitter, fuzzing, and security.
- Media and AI runtime, STT/TTS, IVR, DTMF, barge-in, voice apps, and metrics.
- Technical softphone, profiles, lab hooks, scenario recorder, mixed scenarios, and UI roadmap.
- Implementation roadmap and validation gates.

## Architecture

```text
Applications / CLI / CI / QA / Softphone UI
        |
        v
sipx Harness Core
  Actor, Scenario, Expect, Timeline, Verdict, Artifact, Metrics
        |
        +-------------------------+-------------------------+
        |                         |                         |
        v                         v                         v
 AsteriskBackend            NativeSipBackend            Mock/Replay
 ARI, Stasis, bridges       SIP, SDP, RTP, DTMF         tests, replay
 media, recordings          strict/lab, softphone       fixtures
        |                         |
        v                         v
 Asterisk/PJSIP             SIP endpoints/PBX/SBC/IVR
```

## Main Concepts

| Concept | Meaning |
| --- | --- |
| `Harness` | Runtime that owns configuration, backends, actors, scenario runs, and artifacts. |
| `Actor` | Programmable participant: native softphone, Asterisk, remote SIP target, AI bot, fake carrier, queue. |
| `Scenario` | Executable call flow with steps, fixtures, expectations, and final verdict. |
| `Call` | High-level call facade for apps and tests. |
| `CallLeg` | One leg of a call, such as a SIP dialog or Asterisk channel. |
| `Expectation` | Temporal or deterministic assertion over SIP, SDP, RTP, media, AI, Asterisk, metrics, or timeline. |
| `Timeline` | Ordered event log used for debug, replay, reports, and assertions. |
| `Verdict` | First-class outcome with reason, failures, warnings, metrics, and artifact links. |
| `Artifact` | Persisted evidence: JSONL timeline, WAV, transcript, PCAP, report. |

## Backends

### AsteriskBackend

The first practical backend should use Asterisk where Asterisk is strong:

- PJSIP endpoints and trunks.
- ARI REST commands and ARI WebSocket events.
- Dialplan `Stasis(sipx)` handoff into Python.
- Bridges, queues, recordings, MOH, DTMF, playback, transfers.
- ExternalMedia, AudioSocket, or WebSocket media for AI and STT/TTS.

This backend is the fastest path to IVR automation, AI voice bots, contact-center flows, queue validation, and functional voice testing.

### NativeSipBackend

The native backend is required for what Asterisk intentionally hides or normalizes:

- Raw SIP wire-level assertions.
- Exact headers, CSeq, Via branch, tags, timers, retransmissions.
- Malformed SIP/SDP/RTP tests.
- Fuzzing and parser robustness.
- Technical softphone behavior.
- RTP impairment, payload validation, jitter/loss measurement.

It should have two modes:

| Mode | Purpose |
| --- | --- |
| `strict` | RFC-oriented behavior for real interop and reliable softphone automation. |
| `lab` | Controlled malformed messages, protocol overrides, delayed messages, custom SDP, and fault injection. |

The native SIP/SDP/RTP core should be sans-I/O so protocol logic can be tested without sockets.

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
4. Build `MockBackend` and `sipx` CLI skeleton.
5. Build `AsteriskBackend` with ARI/Stasis.
6. Choose and implement one Asterisk media path.
7. Add media frame, STT/TTS protocols, and barge-in policy.
8. Build minimum `NativeSipBackend` for technical softphone mode.
9. Add reports, replay, and scenario export.
10. Add lab mode, fuzzing, SIP/RTP conformance, and advanced interop.

## Development

Project metadata currently requires Python `>=3.14`.

Expected validation commands:

```bash
ruff format --check .
ruff check .
ty check
pytest
```

Integration tests that require Asterisk must be explicitly configured and must not depend on real secrets committed to the repository.

Useful CLI commands:

```bash
sipx scenario run path/to/scenario.py --artifacts-dir artifacts
sipx scenario export artifacts/<run_id>/timeline.jsonl --format python
sipx replay artifacts/<run_id>/timeline.jsonl
sipx profile list --config harness.toml
sipx profile show lab --config harness.toml
sipx phone register lab --config harness.toml
sipx phone unregister lab --config harness.toml
sipx phone call sip:6000@pbx.lab --profile lab --config harness.toml
sipx phone listen lab --config harness.toml --duration 30
sipx register lab --config harness.toml
sipx register --aor sip:1001@example.com --registrar sip:pbx.example.com:5060 --username 1001 --password secret
sipx call sip:6000@pbx.lab --profile lab --duration 5
```

Phone commands that touch the network require either a profile or explicit `--aor` and `--registrar` flags. If `--remote-host` and `--remote-port` are omitted, `sipx` uses the registrar host and port.

GitHub automation lives under `.github/workflows`:

- `ci.yml` runs uv sync, console-script smoke test, ruff, pytest, and package build.
- `asterisk.yml` starts the local Docker Asterisk lab and runs opt-in integration tests.
- `create-release.yml` creates a draft `v<pyproject version>` release on `master`.
- `release.yml` verifies the release tag, tests, builds, and publishes to PyPI via trusted publishing.

## Asterisk Lab

The repo includes a local Asterisk 22 lab under `docker/asterisk` for backend and Native SIP integration work.

```bash
docker compose -f docker/asterisk/docker-compose.yml up --build
SIPX_ASTERISK_INTEGRATION=1 python -m pytest tests/test_asterisk_integration.py
```

Default lab-only endpoints:

- ARI: `http://127.0.0.1:8088/ari`, user `sipx`, password `sipx`.
- SIP UDP: `127.0.0.1:5060`.
- Native SIP UAS tests: `sip:1000@127.0.0.1:5060` and `sip:1001@127.0.0.1:5060`.

## Security Notes

- Treat recordings and transcripts as sensitive.
- Redact SIP auth headers, ARI credentials, provider tokens, SDP crypto lines, and configured PII before logs/artifacts.
- Keep Python as a separate process from Asterisk loadable modules unless licensing and maintenance tradeoffs are explicitly accepted.
- Use allowlists, CPS limits, consent, and opt-out controls before real outbound calling.
- Prefer TLS/WSS for ARI and media WebSockets in production.
