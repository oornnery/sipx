# DESIGN

## Source Of Truth

This file is the detailed implementation design for `sipx`. `IDEA.md` is historical source material only. There is intentionally no separate `/docs` tree. Implementation context must live in the current project structure: `README.md`, `FORMAT.md`, `SPEC.md`, `DESIGN.md`, `TODO.md`, `.spec/*`, and `.mem/*`.

## Product Identity

`sipx` is a Python Voice/SIP workspace for AI, automation, IVR testing, technical softphones, contact-center apps, and real-time media validation.

It is not only a SIP User Agent, not only a PBX wrapper, and not a normal end-user softphone. The product center is the harness: actors, scenarios, expectations, timelines, verdicts, artifacts, replay, and reports.

```text
Root sipx is SIP protocol/runtime.
The Harness lives in sipx-harness.
Asterisk is a runtime app.
SIP UAC/UAS runtime is the low-level engine.
The workspace Harness is the product.
```

## Product Shape

| Product | Purpose |
| --- | --- |
| Voice Harness | `sipx-harness` scenario runner, `expect`, timeline, artifacts, verdicts, automation, replay, reports. |
| Technical Softphone | SIP/RTP endpoint for engineers, automation, inspection, negative tests, scenario recording. |
| Asterisk Integration Runtime | Asterisk as PBX/media/contact-center engine controlled by Python. |

The root package `sipx` owns SIP protocol/runtime and RTP media primitives. The harness lives in workspace package `apps/harness` as `sipx_harness`. Headless SIP technical softphone ergonomics live in split root `SipUac`/`SipUas` modules instead of a separate wrapper package.

## Main Use Cases

| Use case | Required behavior |
| --- | --- |
| Outbound bot | Act as UAC, send `INVITE`, negotiate SDP, send/receive RTP, speak via TTS, listen via STT, detect DTMF, navigate IVR. |
| Inbound bot | Act as UAS, answer `INVITE`, play IVR prompts, converse with AI, transfer, enqueue, or hang up. |
| IVR tester | Call external IVRs, send RFC4733 DTMF, speak prompts, measure latency, record audio, generate reports. |
| Media/AI framework | Plug STT, TTS, VAD, LLM, recorder, silence detector, intent classifier, scripts, and scenario logic. |
| Technical softphone | Register, call, answer, inspect SIP/SDP/RTP, mutate protocol in lab mode, export evidence. |
| Contact-center app | IVR, queue, bridge, recording, transcript, agent connection, AI assist, QA checks. |

## Mental Model

Earlier mental model:

```text
UserAgent -> Call -> Media -> AI
```

Final mental model:

```text
Harness -> Actors -> Scenarios -> Expectations -> Evidence -> Verdict
              |          |             |            |
              +----------+-------------+------------+
                         SIP/RTP/AI/IVR/Queue/Softphone/Test/Report
```

The call is one part of the scenario. The center of the product is executable behavior and verifiable evidence.

## Operating Modes

| Mode | Purpose |
| --- | --- |
| Scenario mode | Few calls, deep validation, rich evidence, deterministic and semantic expectations. |
| Load mode | Many calls, less AI, focus on CPS, success rate, setup latency, RTP quality, capacity. |
| Exploration mode | AI navigates unknown IVRs, builds graphs, exports deterministic scenarios. |
| App mode | Runs real services: IVR, queue, bot, softphone, B2BUA, contact-center logic. |
| Lab mode | Controlled protocol manipulation, malformed messages, timing faults, media impairment. |

## AI Roles

| Role | Description | Example |
| --- | --- | --- |
| Participant | Listens, decides, speaks, navigates IVR, responds to user. | Conversational bot. |
| Observer | Analyzes audio/transcript/events without controlling call. | Intent, frustration, policy checks. |
| Explorer | Calls unknown IVRs, tries options, discovers menu graph, exports scenario. | IVR map generation. |
| Semantic judge | Validates meaning rather than exact transcript. | `expect(call.speech).to_mean(...)`. |

Semantic AI expectations are probabilistic. They must not be the only pass/fail criterion for critical regressions.

## Non-Goals For MVP

- No carrier-grade PBX replacement.
- No full SIP/RTP stack before harness core exists.
- No GUI before headless engine and CLI prove the model.
- No Asterisk loadable modules in first product path.
- No AI-only pass/fail for critical regressions.
- No video, full WebRTC, or multi-party conferencing in MVP.

## High-Level Architecture

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

Scenarios should describe participants and expectations, not runtime plumbing. A runtime is an execution detail behind an actor.

## Core Entities

| Entity | Responsibility |
| --- | --- |
| `Harness` | Owns config, runtimes, actors, scenario execution, artifacts. |
| `Actor` | Programmable participant: softphone, Asterisk, remote target, bot, queue, fake carrier. |
| `Scenario` | Executable flow with steps, fixtures, expectations, final verdict. |
| `Call` | High-level call facade for apps and tests. |
| `CallLeg` | One side of a call: SIP dialog or Asterisk channel plus media state. |
| `MediaBridge` | Relationship between call legs and media streams. |
| `Expectation` | Condition over SIP, SDP, RTP, media, AI, Asterisk, timeline, or metrics. |
| `Timeline` | Ordered event log for debug, replay, reports, and assertions. |
| `Verdict` | `passed`, `failed`, `error`, or `skipped`, with evidence. |
| `Artifact` | Persisted evidence: timeline, recording, transcript, PCAP, report. |

## Actor-First Model

```python
caller = h.actor("caller").softphone(runtime="sip")
pbx = h.actor("pbx").asterisk(runtime="asterisk_lab")
agent = h.actor("agent").softphone(runtime="sip")
target = h.actor("target").remote("sip:ivr@example.com")
bot = h.actor("bot").ai_agent(policy=my_policy)
```

Actor types:

| Actor | Purpose |
| --- | --- |
| `SipActor` | SIP/RTP endpoint and technical softphone. |
| `AsteriskActor` | Controlled Asterisk PBX/media/runtime actor. |
| `RemoteSipTarget` | External SIP endpoint, PBX, IVR, carrier, SBC, or softphone. |
| `AiBotActor` | AI participant, observer, judge, or navigator. |
| `FakeCarrierActor` | Simulated provider or trunk for tests. |
| `QueueActor` | Queue behavior for contact-center scenarios. |

An actor can use the SIP UAC/UAS runtime, Asterisk, mock, replay, or a future runtime. The scenario should keep the same mental model when the runtime changes.

## Runtime Interfaces

Implemented harness contracts are ABCs: `Runtime`, `CallRuntime`, and `DtmfRuntime`. `MockRuntime` implements the call-control and DTMF contracts as a deterministic test-double for harness tests and local scenario skeletons.

Implemented SIP role contracts are ABCs: `SipWireRuntime`, `SipUacRuntime`, and `SipUasRuntime`. `SipUserAgent` implements all three; `SipUac` and `SipUas` are role-specific subclasses for clearer UAC/UAS test and app code.

```python
class TelephonyRuntime(Protocol):
    async def originate(self, target: str, **opts) -> "Call": ...
    async def accept(self, event: "IncomingCallEvent") -> "Call": ...
    async def answer(self, call: "Call", **opts) -> None: ...
    async def hangup(self, call: "Call", **opts) -> None: ...
    async def send_dtmf(self, call: "Call", digits: str, **opts) -> None: ...
    async def bridge(self, a: "Call", b: "Call", **opts) -> "Bridge": ...
    async def start_media_stream(self, call: "Call") -> "MediaStream": ...
    def events(self) -> AsyncIterator["HarnessEvent"]: ...
```

```python
class SipWireControl(Protocol):
    async def send_request(self, request: "SipRequest") -> None: ...
    async def send_response(self, response: "SipResponse") -> None: ...
    def events(self) -> AsyncIterator["SipWireEvent"]: ...
```

```python
class MediaControl(Protocol):
    async def start(self) -> None: ...
    async def recv_frame(self) -> "AudioFrame": ...
    async def send_frame(self, frame: "AudioFrame") -> None: ...
    async def send_dtmf(self, digit: str) -> None: ...
```

`AsteriskRuntime` implements high-level call control and parts of media control. `SipUserAgent`/`SipUac`/`SipUas` implement high-level call control, SIP wire control, and media control.

## Runtime Types

| Runtime | Purpose |
| --- | --- |
| `AsteriskRuntime` | Fast MVP, real trunks/endpoints, bridges, queues, recordings, media server, contact center. |
| `SipUserAgent` | Raw SIP/SDP/RTP, technical softphone, lab mode, malformed messages, fuzzing, conformance. |
| `MockRuntime` | Unit and scenario tests without network. |
| `ReplayRuntime` | Replay recorded timelines/artifacts for debugging and regression. |
| `PjsipRuntime` | Optional future robust softphone runtime, less suitable for wire-level lab control. |
| `SippRuntime` | Optional future load/conformance helper, not core public API. |

## Capability Model

Every runtime must declare capabilities.

```python
class RuntimeCapability(StrEnum):
    HIGH_LEVEL_CALL_CONTROL = "high_level_call_control"
    RAW_SIP = "raw_sip"
    RAW_RTP = "raw_rtp"
    MALFORMED_SIP = "malformed_sip"
    REGISTER = "register"
    BRIDGE = "bridge"
    QUEUE = "queue"
    RECORDING = "recording"
    EXTERNAL_MEDIA = "external_media"
    MEDIA_IMPAIRMENT = "media_impairment"
    PCAP = "pcap"
    AI_MEDIA = "ai_media"
```

Example capability sets:

```python
AsteriskRuntime.capabilities = {
    HIGH_LEVEL_CALL_CONTROL,
    BRIDGE,
    QUEUE,
    RECORDING,
    EXTERNAL_MEDIA,
    AI_MEDIA,
}

SipUserAgent.capabilities = {
    HIGH_LEVEL_CALL_CONTROL,
    RAW_SIP,
    RAW_RTP,
    REGISTER,
    MALFORMED_SIP,
    MEDIA_IMPAIRMENT,
    PCAP,
    AI_MEDIA,
}
```

If an expectation is unsupported, fail loud:

```text
UnsupportedExpectation:
AsteriskRuntime does not expose raw SIP wire-level Via branch.
Use `SipUserAgent`/`SipUac`/`SipUas` or enable passive packet capture.
```

## Responsibility Matrix

| Responsibility | Where it belongs |
| --- | --- |
| Scenarios, expectations, timeline, reports | Python harness core. |
| STT, TTS, LLM, VAD, semantic analysis | App/runtime packages on top of root media primitives. |
| Enriched recording, transcript, artifacts | Python harness core. |
| User-facing SDK | Python harness core. |
| Raw SIP validation | `SipUserAgent`. |
| Malformed message tests | `SipUserAgent`. |
| Real SIP trunks | Asterisk first. |
| Queues, MOH, bridge, production call handling | Asterisk first. |
| Product IVR logic | Python controlling Asterisk through ARI first. |
| Headless softphone automation | Python SIP first, optional PJSIP later. |
| Real-time AI media | Python plus Asterisk ExternalMedia, AudioSocket, WebSocket, or RTP. |
| Massive SIP traffic | SIPp, Kamailio, OpenSIPS, Asterisk, or specialized tools. |
| High-volume SBC/proxy/registrar | Kamailio/OpenSIPS, not `sipx` MVP. |

## AsteriskRuntime

Use Asterisk where it accelerates the product:

- Receive SIP calls.
- Originate calls.
- Register endpoints through PJSIP.
- Connect SIP trunks.
- Handle common NAT and interop behavior.
- Bridge channels.
- Play audio.
- Record.
- Route calls.
- Hold queues.
- Play music on hold.
- Detect and send DTMF.
- Transcode codecs.
- Transfer calls.
- Integrate with existing PBX environments.

Primary interface choices:

| Interface | Use for | Avoid for |
| --- | --- | --- |
| ARI | Main call control, channels, bridges, endpoints, app-level IVR, bots, B2BUA behavior. | Generic PBX administration. |
| ExternalMedia | RTP/media to and from Python for STT/TTS/AI. | Business rules. |
| WebSocket media | Easier bidirectional media with less RTP timing work. | Raw RTP conformance. |
| AudioSocket | Simple bidirectional PCM and DTMF path. | Raw RTP conformance. |
| AMI | Monitoring, legacy events, simple originate, dashboards. | Real-time media pipeline. |
| AGI/FastAGI | Simple dialplan scripts. | Modern streaming AI/harness core. |
| Dialplan | Initial routing, fallback, security contexts, Stasis entry. | Complex product logic. |

## Asterisk Roles

| Role | Description |
| --- | --- |
| Controlled runtime | Python controls Asterisk through ARI. |
| System under test | A `sipx` SIP softphone registers or calls into Asterisk to validate it from outside. |
| Scenario resource | Asterisk is one actor inside a mixed SIP/Asterisk/remote scenario. |

## Asterisk Main Flow

```text
SIP trunk / endpoint / softphone
          |
          v
      Asterisk
  PJSIP, channels, bridges,
  queues, RTP, codecs, recording
          |                 |
          | ARI             | External media
          v                 v
      Python sipx Harness
  scenarios, expect, AI, IVR logic,
  STT, TTS, reports, timeline
```

## Asterisk Media Options

MVP selection: WebSocket media. AudioSocket and ExternalMedia RTP remain future paths.

| Media path | Use |
| --- | --- |
| WebSocket media | Preferred if available; avoids manual RTP timing burden and can support TLS and flow control. |
| AudioSocket | Simple bidirectional PCM and DTMF path; good for early AI MVP. |
| ExternalMedia RTP | Best when real RTP behavior matters; more timing and RTP work in Python. |

Suggested implementation order:

1. WebSocket media or AudioSocket for fast AI media MVP.
2. ExternalMedia RTP when RTP stats, packet timing, or protocol validation matters.
3. RTP in `SipUserAgent` for protocol-lab work.

## Asterisk Inbound AI Flow

The minimal inbound `Stasis(sipx)` example lives in workspace package `apps/asterisk` as `sipx_asterisk.stasis`.

```text
1. Customer calls DID.
2. Asterisk receives via PJSIP trunk.
3. Dialplan sends channel to Stasis(sipx,inbound_ivr).
4. Python receives StasisStart.
5. Python answers channel through ARI.
6. Python creates a mixing bridge.
7. Python adds customer channel to bridge.
8. Python creates ExternalMedia/WebSocket/AudioSocket channel.
9. Python adds media channel to bridge.
10. Customer audio flows to STT.
11. TTS/AI audio flows back to bridge.
12. Python controls DTMF, barge-in, menu, queue, transfer, and hangup.
```

Pseudo-code:

```python
@h.app("inbound")
async def inbound(call):
    await call.answer()

    await call.attach_media(
        mode="websocket",
        codec="slin16",
        direction="both",
    )

    await call.say("Hello, how can I help?", barge_in=True)

    async for user_turn in call.conversation():
        response = await agent.respond(user_turn.text)
        await call.say(response.text, barge_in=True)
```

## Asterisk Outbound IVR Test Flow

```text
1. Python asks Asterisk to originate a call.
2. Asterisk calls SIP trunk or endpoint.
3. When answered, channel enters ARI/Stasis app.
4. Python attaches media.
5. Python listens for prompts through STT.
6. Python sends DTMF or speech through TTS.
7. Expectations validate SIP, media, timing, and behavior.
8. Python generates report and artifacts.
```

Example:

```python
@scenario("asterisk_ivr_second_copy")
async def test_ivr(h: Harness):
    call = await h.originate(
        endpoint="PJSIP/trunk/551140001234",
        app_args={"scenario": "ivr_second_copy"},
    )

    await expect(call).to_answer().within(30)
    await expect(call.rtp).to_flow().within(3)

    await expect(call.media).to_hear(
        "invoice copy",
        mode="semantic",
        confidence=0.85,
    ).within(15)

    await call.dtmf.send("2")
    await expect(call.media).to_hear("document number").within(10)

    await call.dtmf.send("12345678901#")
    await expect(call.media).to_mean(
        "the invoice copy request was accepted",
        confidence=0.85,
    ).within(20)
```

## Minimal Asterisk Config

`http.conf`:

```ini
[general]
enabled = yes
bindaddr = 127.0.0.1
bindport = 8088
```

`ari.conf`:

```ini
[general]
enabled = yes
pretty = no

[sipx]
type = user
read_only = no
password = ${ARI_PASSWORD}
```

`extensions.conf`:

```ini
[sipx-inbound]
exten => _X.,1,NoOp(sipx inbound)
 same => n,Stasis(sipx,inbound,${EXTEN})
 same => n,Hangup()
```

Conceptual `pjsip.conf`:

```ini
[transport-udp]
type=transport
protocol=udp
bind=0.0.0.0:5060

[trunk]
type=endpoint
transport=transport-udp
context=sipx-inbound
disallow=all
allow=ulaw,alaw
aors=trunk
```

Real PJSIP config depends on trunk, auth, NAT, identification, and deployment policy.

## Asterisk Expectations

```python
await expect(call.ari).event("StasisStart").within(1)
await expect(call).to_answer().within(30)
await expect(call.channel).state("Up")
await expect(call.bridge).to_exist()
await expect(call.media).to_flow().within(3)
await expect(call.dtmf).to_receive("1")
await expect(call.rtp_stats).loss_below(1.0)
await expect(call.transcript).to_contain("document")
await expect(call).to_hangup_cleanly()
```

## Asterisk Limitation

Asterisk normalizes and hides raw protocol details. That is good for product behavior and bad for protocol conformance.

Use `SipUserAgent`/`SipUac`/`SipUas` instead of `AsteriskRuntime` when validating:

- Exact retransmission behavior.
- Exact `Via` branch.
- Malformed `CSeq`.
- Invalid SDP.
- Out-of-order provisional responses.
- Proxy-specific behavior.
- Parser robustness.
- RFC transaction compliance.
- Compact headers and edge cases.
- Malformed SIP.
- Content-Length mismatch.
- RTP sequence gaps, strange timestamps, unknown payload types.

## SipUserAgent / SipUac / SipUas

The SIP user-agent runtime gives `sipx` its identity as a SIP harness, not only an Asterisk app.

Responsibilities:

- Build raw `INVITE` requests.
- Receive raw responses.
- Control `Via`, branch, `CSeq`, tags, headers, and SDP.
- Retransmit UDP according to transaction timers.
- Validate timers.
- Own SDP offer/answer.
- Own RTP packetization and depacketization.
- Own DTMF RFC4733.
- Run malformed scenarios.
- Provide technical softphone behavior.

High-level ergonomics belong in separate role files:

- `sipx/uac.py`: outbound identity, REGISTER, OPTIONS, MESSAGE, generic request, call, BYE, INFO, re-INVITE, RTP send policy.
- `sipx/uas.py`: inbound listen/answer/reject, SDP answer, ACK wait, BYE answer, inbound re-INVITE, RTP receive/playout policy.
- `sipx/ua.py`: shared UDP transport, dialog, transaction, retransmission, auth, and low-level SIP runtime behavior.

Modes:

| Mode | Purpose |
| --- | --- |
| `strict` | RFC-oriented, reliable, real interop, calls that should behave like a normal endpoint. |
| `lab` | Controlled protocol mutation, delayed messages, malformed headers, custom SDP, fault injection. |

Lab hook shape:

- `SipHooks.before_send_message` may mutate or replace outbound SIP messages, or return raw bytes for malformed SIP.
- `SipHooks.before_sdp_body` may rewrite SDP bodies before serialization.
- `SipHooks.after_receive_event` may observe, replace, or drop received wire events.
- `SipHooks.retransmission_intervals` may override transaction timer intervals.
- Hooks are rejected in `strict` mode and are available only in `lab` mode.

## Protocol Normative Base

| Layer | Standard |
| --- | --- |
| SIP core | RFC 3261 |
| SIP timers | RFC 3261 T1/T2/T4 and timers A-K |
| SDP | RFC 8866 |
| SDP Offer/Answer | RFC 3264 |
| RTP/RTCP | RFC 3550 |
| RTP/AVP static payloads | RFC 3551 |
| DTMF over RTP | RFC 4733 |
| SIP digest | RFC 8760 |
| Session timers | RFC 4028 |
| PRACK / 100rel | RFC 3262 |
| UPDATE | RFC 3311 |
| SIP INFO | RFC 6086, optional compatibility path |
| SRTP | RFC 3711 |
| SDP crypto for SRTP | RFC 4568 |
| ICE/NAT traversal | RFC 8445, optional/future |
| SIP over WebSocket | RFC 7118, optional/future |

## Protocol MVP Scope

The first implementation should support audio only. Video, multi-party conferencing, full WebRTC, and carrier-grade B2BUA behavior are outside the MVP.

| Area | MVP requirement |
| --- | --- |
| SIP | `INVITE`, `ACK`, `BYE`, `CANCEL`, final and provisional responses, basic UAC/UAS. |
| Transactions | INVITE and non-INVITE state machines, timers, UDP retransmission. |
| Dialog | `Call-ID`, `From` tag, `To` tag, `CSeq`, `Contact`, `Route`, `Record-Route`. |
| SDP | Parser/serializer, `m=audio`, `c=`, `a=rtpmap`, `a=fmtp`, media direction. |
| Offer/Answer | Codec choice, dynamic payload type, RTP port, `telephone-event`. |
| RTP | RTP v2 send/receive, sequence, timestamp, SSRC, marker, payload type. |
| Codecs | PCMU/8000, PCMA/8000, internal PCM. |
| DTMF | Send and receive `telephone-event` via RFC4733. |
| AI | Streaming STT, streaming TTS, VAD, interruption/barge-in. |
| IVR | Play audio/TTS, collect digits, timeouts, interdigit timeout, menu, fallback. |
| Tests | Deterministic UAC/UAS scenarios, loss/jitter/reorder simulation. |

## Sans-I/O Rule

SIP protocol core must be sans-I/O.

Core sans-I/O modules:

- SIP parser and serializer.
- SIP transaction state machines.
- Dialog state and route sets.
- SDP parser and serializer.
- Offer/answer logic.
- RTP packet parse/serialize.
- DTMF event parser.
- Jitter buffer logic.

Runtime async modules:

- UDP/TCP/TLS/WebSocket sockets.
- Timers and scheduled retransmission.
- STT/TTS streaming.
- Recording.
- Provider integrations.

## UAC Call State

```text
IDLE
  | invite()
  v
CALLING
  | 100 Trying
  v
PROCEEDING
  | 180 Ringing / 183 Session Progress
  | 183 with SDP may allow early media by policy
  v
EARLY
  | 200 OK + SDP answer
  v
CONFIRMED
  | send ACK
  | start or continue RTP
  v
ACTIVE
  | local or remote BYE
  v
TERMINATING
  | 200 OK for BYE
  v
TERMINATED
```

## UAS Call State

```text
IDLE
  | INVITE + SDP offer
  v
INVITE_RECEIVED
  | 100 Trying
  | validate headers, auth, SDP, codecs
  v
EARLY
  | 180 Ringing or 183 Progress
  v
ACCEPTING
  | 200 OK + SDP answer
  v
WAIT_ACK
  | ACK
  v
ACTIVE
  | bot / IVR / media
  v
TERMINATED
```

## SIP Timers

RFC 3261 transaction timers must be explicit. Do not scatter `asyncio.sleep()` calls through call-control logic.

Important base timers:

| Timer | Default |
| --- | --- |
| T1 | 500 ms |
| T2 | 4 s |
| T4 | 5 s |

The implementation must model timers A-K for retransmission and timeout behavior.

## SDP And Offer/Answer

SDP describes sessions. It is not a magic negotiator. Offer/answer selects the shared view of media: type, remote IP and port, payload types, codec parameters, direction, and telephone-event support.

MVP SDP fields:

- `v=`
- `o=`
- `s=`
- `c=`
- `t=`
- `m=audio`
- `a=rtpmap`
- `a=fmtp`
- `a=sendrecv|sendonly|recvonly|inactive`

## RTP Outbound

```text
MediaClock starts at first frame.

For each frame:
  payload = encode(frame)
  packet = RTP(
      version=2,
      payload_type=negotiated_pt,
      sequence=seq++,
      timestamp=rtp_ts,
      ssrc=local_ssrc,
      marker=marker_policy,
  )
  rtp_ts += samples_per_frame
  sendto(packet)
```

The packet clock should use monotonic time and drift correction, not blind `asyncio.sleep(0.02)`.

```python
next_deadline_ns += frame_duration_ns
delay = max(0, next_deadline_ns - time.monotonic_ns())
await sleep_ns(delay)
```

## RTP Inbound

```text
on_udp_datagram:
  parse RTP
  validate version/PT/SSRC
  update sequence stats
  if PT == telephone-event: dtmf decoder
  else: jitter_buffer.insert(packet)

jitter playout loop:
  packet = jitter_buffer.pop_due()
  frame = decode(packet.payload)
  emit AudioFrame
```

RTP provides payload type, sequence, timestamp, and monitoring through RTCP. It does not guarantee delivery, order, latency, or QoS. `sipx` must provide jitter buffer, loss tolerance, stats, and metrics.

Implemented RTP primitives now include PCMU/PCMA encode/decode without `audioop`, synthetic `silence`/`noise` PCM sources, optional lazy PyAudio input, `RtpSequenceStats` jitter/loss/duplicate counters, `RtpMetrics` tx/rx snapshots, `RtpJitterBuffer` ordered playout with concealment and underrun/overrun/late/duplicate counters, and `RtpAudioSession` for UDP RTP send/receive with metrics snapshots. High-level `SipUac.call(audio="none|silence|noise|pyaudio")` and `SipUas.answer(audio="none|silence|noise|pyaudio")` support no-device synthetic media or optional PyAudio during calls and separate RTP bind host from SDP advertised host. UAS answers use `SipProvisionalResponse` for `0+` configured RFC 3261 `1xx` responses before the final response, including direct final-only flows and `100 + 183/SDP + 200`. The root `sipx` CLI exposes `--audio`, `--jitter-buffer-ms`, `--rtp-stats`, and `--metrics-json` on `call`/`listen`.

## Jitter Buffer

Initial config:

```python
JitterConfig(
    initial_delay_ms=40,
    min_delay_ms=20,
    max_delay_ms=120,
    adaptive=True,
    max_late_packets=50,
)
```

Policy:

| Situation | Action |
| --- | --- |
| Late packet | Drop and increment metric. |
| Small gap | Simple PLC, silence, or short repetition. |
| Reorder | Reorder up to buffer limit. |
| SSRC change | Validate collision/change and emit event. |
| Unknown payload type | Drop and rate-limit log. |

## Codecs

MVP:

| Codec | Use |
| --- | --- |
| PCMU | SIP/PSTN interoperability. |
| PCMA | SIP/PSTN interoperability. |
| PCM s16le | Internal STT/TTS/resample format. |

Future:

| Codec | Reason |
| --- | --- |
| Opus | Better quality and bandwidth on IP networks. |
| G.722 | Common wideband VoIP. |
| CN | Comfort noise. |
| L16 | Lab/testing. |

Do not depend on stdlib `audioop` for G.711. It was removed in Python 3.13. Implement PCMU/PCMA directly or use an explicit compatible package/C extension.

## DTMF

DTMF is a media event, not a loose character.

Input sources:

| Source | Status |
| --- | --- |
| RTP `telephone-event` RFC4733 | Primary. |
| SIP INFO | Optional compatibility path. |
| In-band tone detection | Optional, expensive, legacy path. |

Internal event:

```python
@dataclass(slots=True, frozen=True)
class DtmfEvent:
    digit: str
    duration_ms: int
    volume: int | None
    started_at_ns: int
    ended: bool
    source: Literal["rtp4733", "sip_info", "inband"]
```

## SIP Digest

UAC behavior:

```text
receive 401/407
choose best supported algorithm
recalculate Authorization or Proxy-Authorization
resend with correct CSeq behavior
```

UAS behavior:

```text
challenge with WWW-Authenticate or Proxy-Authenticate
prefer SHA-256 or SHA-512/256
allow MD5 only in compatibility mode
```

## SRTP

SRTP should be a separate module.

```python
MediaSecurity(
    mode="srtp",
    keying="sdes",
    crypto_suites=["AES_CM_128_HMAC_SHA1_80"],
)
```

DTLS-SRTP is future work.

## NAT And Interop

MVP controlled environments should support UDP first. TCP can follow early. Later interop features:

| Feature | When |
| --- | --- |
| `rport`, `received`, symmetric RTP/latching | Real SIP interop. |
| REGISTER client | Trunk/proxy authentication. |
| Outbound/keepalive | UAs behind NAT. |
| ICE/STUN/TURN | Complex NAT. |
| SIP over WebSocket | Browser/web deployment. |
| TLS/SIPS | Production. |

## Performance Rules

Hot RTP path rules:

- Avoid Pydantic in packet path.
- Use `dataclasses(slots=True)`.
- Use `memoryview` and `bytearray`.
- Use `struct.pack_into` and `struct.unpack_from`.
- Use `recvfrom_into` where possible.
- Use pools or ring buffers for frames.
- Avoid large allocations every 20 ms.
- Separate signaling tasks and media tasks.
- Never call LLM/STT/TTS synchronously in RTP loop.
- Keep metrics non-blocking.

## Fuzzing Targets

Mandatory fuzz/property targets:

- SIP start line.
- SIP headers.
- URI parser.
- SDP parser.
- RTP packet parser.
- Telephone-event parser.

Network-exposed protocol parsers must fail closed with typed errors, no crash, and no unbounded memory consumption.

## Public API Center

The public API centers on actors and scenarios, not on `UserAgent` directly.

```python
from sipx_harness import Harness, expect, scenario


async with Harness.from_file("harness.toml") as h:
    caller = h.actor("caller").softphone(profile="lab")
    target = h.actor("target").remote("sip:ivr@example.com")

    call = await caller.call(target)
```

`UserAgent` remains an internal or low-level piece under actors.

## Harness Creation

```python
h = Harness()

h.register_runtime(
    "asterisk_lab",
    AsteriskRuntime(
        ari_url="http://127.0.0.1:8088/ari",
        app="sipx",
        username="sipx",
        password="${ARI_PASSWORD}",
    ),
)

h.register_runtime(
    "sip",
    SipUserAgent(
        bind=("0.0.0.0", 5062),
        rtp_ports=(20000, 30000),
        mode="strict",
    ),
)
```

## Python Scenario DSL

```python
@scenario("ivr_second_copy")
async def ivr_second_copy(h: Harness) -> None:
    caller = h.actor("caller").softphone(profile="lab")
    target = h.actor("target").remote("sip:ivr@example.com")

    call = await caller.call(target)

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

## YAML Scenario DSL

YAML scenarios are useful for QA teams and non-developer users.

```yaml
name: ivr_second_copy
actors:
  caller:
    type: softphone
    profile: lab
  target:
    type: remote
    uri: sip:ivr@example.com

steps:
  - call:
      from: caller
      to: target

  - expect:
      sip.final_response: 200
      within: 30s

  - expect:
      rtp.flow: true
      within: 2s

  - expect:
      media.hear:
        text: welcome
        mode: contains
      within: 8s

  - send_dtmf: "2"

  - expect:
      media.meaning: the IVR asked for the customer document number
      confidence: 0.85
      within: 10s

  - send_dtmf: "12345678901#"

  - expect:
      media.meaning: the IVR confirmed the second-copy request
      confidence: 0.85
      within: 20s

  - hangup: true
```

## Interactive Exploration

```python
graph = await h.explore_ivr(
    target="sip:ivr@example.com",
    max_depth=5,
    strategy="ai",
    allowed_digits="1234567890#*",
)

graph.save("ivr_graph.json")
graph.render("ivr_graph.html")
graph.export_scenario("ivr_second_copy.yml")
```

## Requests-Like SIP API

For quick scripts, `sipx` should provide a simple `InviteResult` shape.

```python
r = await h.sip.invite("sip:1000@pbx.local")

assert r.status_code == 200
assert r.history.has(100)
assert r.history.has_any(180, 183)
assert r.sdp.has_media("audio")
assert r.sdp.has_codec("PCMU")

call = r.call
await call.dtmf.send("1#")
```

`status_code` means final SIP response for the initial `INVITE`, not the whole call lifecycle.

```python
@dataclass(slots=True)
class InviteResult:
    status_code: int
    reason: str
    final_response: SipResponse
    provisional_responses: list[SipResponse]
    request: SipRequest
    dialog: Dialog | None
    call: Call | None
    sdp_offer: SessionDescription | None
    sdp_answer: SessionDescription | None
    duration_ms: int
    timeline: Timeline
```

## Transaction-Level API

SIP `INVITE` is not equivalent to HTTP request/response. Some tests need transaction-level control.

```python
tx = await h.sip.start_invite("sip:ivr@example.com")

await tx.expect_response(100).optional()
await tx.expect_response(180, 183).within(10)

final = await tx.expect_final_response().within(30)

if final.status_code == 200:
    call = await tx.ack()
else:
    raise AssertionError(f"INVITE failed: {final.status_code}")
```

After final response, behavior continues through ACK, dialog, media, BYE, re-INVITE, UPDATE, CANCEL, REFER, INFO, and session timers.

## Expect Families

```python
expect(call.sip)
expect(call.dialog)
expect(call.sdp)
expect(call.rtp)
expect(call.rtcp)
expect(call.dtmf)
expect(call.media)
expect(call.speech)
expect(call.ivr)
expect(call.queue)
expect(call.ai)
expect(call.asterisk)
expect(call.recording)
expect(call.metrics)
expect(call.timeline)
expect(call.bridge)
```

Examples:

```python
await expect(call.sip).response(100).optional()
await expect(call.sip).response(180, 183).within(5)
await expect(call.sip).final_response(200).within(30)
await expect(call.sip).to_send("ACK").after_response(200)
await expect(call.sip).to_receive_method("BYE").not_before(10)
await expect(call.sdp).to_have_codec("PCMU")
await expect(call.sdp).to_have_dtmf_transport("telephone-event")
await expect(call.rtp).to_flow().within(2)
await expect(call.rtp).packet_loss_below(1.0)
await expect(call.dtmf).to_use_rfc4733()
await expect(call.media).to_not_have_dead_air(longer_than=5)
await expect(call.speech).to_mean("the second copy of the invoice was requested")
await expect(call.queue).to_connect_agent().within(120)
await expect(call.bridge).to_have_two_way_audio()
```

## Expect Types

| Type | Use |
| --- | --- |
| Deterministic | SIP status, headers, SDP, RTP, DTMF, regex, audio presence. |
| Temporal | Answer time, RTP start, queue connection, no BYE during window. |
| Probabilistic | STT, AI classification, semantic meaning, anomaly detection. |
| Statistical | Load test success rate, p95 answer time, RTP loss percent. |

Critical regressions need deterministic or temporal checks. Probabilistic checks can enrich the verdict but must not be the only critical gate.

## Verdict

Do not rely only on exceptions. Every scenario should return a first-class verdict.

```python
@dataclass(slots=True)
class Verdict:
    status: Literal["passed", "failed", "error", "skipped"]
    reason: str | None
    failed_expectations: list[ExpectationResult]
    warnings: list[str]
    artifacts: list[Artifact]
    metrics: dict[str, object]
```

## Rich Failure Format

SIP failure example:

```text
FAILED: expected final SIP response 200 within 30s

Observed:
  100 Trying at +32ms
  180 Ringing at +401ms
  486 Busy Here at +2910ms

Request:
  INVITE sip:1000@pbx.local
  Call-ID: abc123
  CSeq: 1 INVITE

Artifacts:
  timeline.jsonl
  sip_messages.txt
  pcap.pcapng
```

Media failure example:

```text
FAILED: expected prompt semantically matching "enter your document number" within 10s

Observed transcript:
  +2.1s "welcome to support"
  +4.8s "press two for invoice copies"
  +11.5s silence timeout

RTP:
  first packet: +91ms
  loss: 0.0%
  avg jitter: 4.2ms
```

## Timeline

Every meaningful action becomes a timeline event.

```python
@dataclass(slots=True)
class TimelineEvent:
    ts_ns: int
    run_id: str
    actor_id: str | None
    call_id: str | None
    leg_id: str | None
    category: str
    name: str
    data: dict
```

Required categories:

- `sip`
- `sdp`
- `rtp`
- `rtcp`
- `dtmf`
- `media`
- `stt`
- `tts`
- `ai`
- `ivr`
- `queue`
- `bridge`
- `asterisk`
- `assertion`
- `artifact`
- `system`

Unified example:

```text
+0000ms  sip.tx        INVITE sip:ivr@pbx.lab
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

For Asterisk, the same timeline may include ARI events:

```text
+0000ms  ari.event     StasisStart channel=...
+0020ms  ari.command   answer channel=...
+0040ms  ari.command   create_bridge
+0050ms  ari.command   add_channel
+0060ms  ari.command   external_media
```

Timeline data must correlate SIP Call-ID, local/remote tags, local/remote SSRC, RTP port, Asterisk channel ID, bridge ID, recording ID, transcript ID, scenario ID, actor ID, and call leg ID when available.

## Artifacts

Minimum per scenario:

- `timeline.jsonl`
- verdict data

Optional by config:

- `recording.wav`
- `transcript.json`
- `sip_messages.txt`
- `pcap.pcapng`
- `report.html`
- `report.txt`

Report sections:

- Verdict.
- SIP final response and history.
- Answer time.
- BYE clean status.
- RTP first packet time.
- Packet loss.
- Average jitter.
- Dead air detection.
- Prompt matches.
- Semantic verdicts.
- Artifact links.

## Media Pipeline

```text
RTP inbound
  -> RTP parser
  -> sequence tracker
  -> jitter buffer
  -> depacketizer
  -> decoder G.711/Opus
  -> internal mono PCM
  -> resampler for STT
  -> VAD / endpointing
  -> streaming STT
  -> transcript events
  -> IVR / Agent / LLM
  -> streaming TTS
  -> resampler for negotiated codec
  -> encoder
  -> RTP packetizer
  -> RTP outbound
```

The core rule is streaming in both directions. Never block outbound RTP waiting for an LLM, STT, or TTS provider.

## AudioFrame

```python
@dataclass(slots=True)
class AudioFrame:
    pcm: memoryview
    sample_rate: int
    channels: int
    duration_ms: int
    timestamp_ns: int
    source: Literal["rtp", "tts", "file", "tone", "silence"]
```

For classic telephony, 20 ms frames are practical. With G.711 at 8 kHz, 20 ms means 160 samples and 160 bytes of PCMU/PCMA payload.

## Media Ports

```python
class MediaPort(Protocol):
    async def recv_frame(self) -> AudioFrame: ...
    async def send_frame(self, frame: AudioFrame) -> None: ...
    async def close(self) -> None: ...
```

Implementations:

| Port | Runtime |
| --- | --- |
| `RtpMediaPort` | `SipUserAgent`. |
| `AsteriskExternalRtpPort` | Asterisk ExternalMedia RTP. |
| `AsteriskWebSocketPort` | Asterisk `chan_websocket`. |
| `AudioSocketPort` | Asterisk AudioSocket. |
| `FileMediaPort` | Tests and replay. |
| `SyntheticMediaPort` | Tones, silence, noise, prompts. |

## STT And TTS Interfaces

STT/TTS protocols live in app packages, not root `sipx.media`. Root media owns only generic audio frames, media ports, and barge-in policy.

```python
from sipx_stt import SttEngine, SttStream, TranscriptEvent
from sipx_tts import TtsEngine


class SttEngine(Protocol):
    async def start(self, *, sample_rate: int, language: str) -> "SttStream": ...


class SttStream(Protocol):
    async def push_audio(self, frame: AudioFrame) -> None: ...
    async def events(self) -> AsyncIterator["TranscriptEvent"]: ...
    async def close(self) -> None: ...


class TtsEngine(Protocol):
    async def synthesize_stream(
        self,
        text: str,
        *,
        voice: str,
        sample_rate: int,
    ) -> AsyncIterator[AudioFrame]: ...
```

## Conversation Events

```python
CallEvent = (
    SipEvent
    | MediaStarted
    | MediaEnded
    | DtmfEvent
    | SpeechStarted
    | SpeechPartial
    | SpeechFinal
    | SilenceTimeout
    | TtsStarted
    | TtsInterrupted
    | Hangup
)
```

## Barge-In

Barge-in is prompt policy.

```python
await call.say(
    "For support, say support or press 2.",
    interruptible=True,
)
```

When VAD/STT detects speech or DTMF during an interruptible prompt:

1. Cancel current TTS.
2. Clear outbound audio queue.
3. Mark prompt as interrupted.
4. Continue STT to finish user turn.
5. Deliver event to IVR or agent logic.

If the agent is slow, send silence, comfort tone, or configured waiting prompt. Do not block the media clock.

## DTMF And IVR

Output to navigate IVRs:

```python
await call.dtmf.send("1234#", mode="rtp", digit_ms=120, gap_ms=80)
await call.say("This is an automated IVR test.")
await call.wait_for_speech_or_digits(timeout=5)
```

Collect digits:

```python
digits = await call.collect_digits(
    prompt="Enter your document number followed by hash.",
    min_digits=11,
    max_digits=11,
    terminators={"#"},
    timeout=8.0,
    interdigit_timeout=2.0,
    barge_in=True,
)
```

Collect speech and digits in the same mechanism:

```python
result = await call.collect(
    prompt="Say sales, support, or finance.",
    grammar=["sales", "support", "finance"],
    digits={"1": "sales", "2": "support", "3": "finance"},
    timeout=7.0,
    barge_in=True,
)
```

## AI As Participant

```text
Person / IVR <-> AI bot
```

The AI listens, understands, speaks, decides, navigates IVR, and responds to the user.

## AI As Observer

```text
Call audio/transcript/events -> AI observer -> labels/verdicts
```

```python
await expect(call.ai_observer).to_classify_intent("invoice_copy")
await expect(call.ai_observer).to_detect_frustration(below=0.3)
await expect(call.ai_observer).to_flag_policy_violation(False)
```

## AI As IVR Explorer

The harness can call an unknown IVR, listen, try options, discover menus, and export a graph.

```text
Initial menu
  1 -> sales
  2 -> support
      1 -> invoice copy
      2 -> human agent
  3 -> finance
```

```python
scenario = DiscoveredIvrScenario.from_call(recording)
scenario.export("finance_ivr.yml")
```

## AI As Semantic Judge

```python
await expect(call.speech).to_mean(
    "the IVR confirmed that the invoice copy will be sent",
    confidence=0.85,
)
```

This is useful but probabilistic. Robust tests should combine it with deterministic assertions: SIP status, headers, SDP, RTP flow, DTMF, timing, regex, and audio presence.

## LLM Provider Clients

The implemented LLM provider surface starts with `LLMChatClient` in workspace package `apps/llm` as `sipx_llm.LLMChatClient`. It uses stdlib HTTP against an OpenAI-compatible `/chat/completions` endpoint with an injectable transport so unit tests do not call the network. Live validation is explicitly opt-in through `SIPX_LLM_API_KEY`, `SIPX_LLM_BASE_URL`, and `SIPX_LLM_MODEL`; no provider key belongs in examples, tests, logs, artifacts, or committed config.

Example templates live in `apps/llm/examples`, `apps/asterisk/examples`, and `apps/scenarios/examples`. They are templates only: they import without secrets and skip or no-op when `SIPX_LLM_API_KEY` is absent.

## Voice Apps

Contact-center and IVR applications should look like a small framework.

```python
app = VoiceApp()


@app.route("sip:support@example.com")
async def support(call: IncomingCall):
    await call.answer()

    choice = await call.menu(
        prompt="For sales say sales or press 1. For support say support or press 2.",
        options={
            "1": "sales",
            "2": "support",
            "sales": "sales",
            "support": "support",
        },
        barge_in=True,
    )

    if choice == "sales":
        await call.enqueue("sales")
    elif choice == "support":
        await call.enqueue("support")
```

Queue example:

```python
queue = Queue(
    name="support",
    strategy="least_recent",
    max_wait=300,
    music_on_hold="moh.wav",
    periodic_prompt="Your call is important to us.",
)

await queue.join(call)
```

Bridge to agent:

```python
agent = await queue.pick_agent()
leg_b = await call.dial(agent.uri)
await call.bridge(leg_b, record=True, transcribe=True)
```

## Technical Softphone

The technical softphone is not an end-user softphone. It is closer to a Postman or Playwright for voice, with SIP/RTP inspection and scenario automation.

```text
technical softphone behavior = SipUac/SipUas + MediaEngine + ScenarioRunner + Inspector
```

It must be built into `SipUac`/`SipUas` on top of `SipUserAgent`, not as a separate redundant wrapper and not on Asterisk. Asterisk can be a runtime, peer, lab PBX, scenario resource, or system under test.

## Technical Softphone Engine

The softphone must be headless first.

```text
Technical Softphone UI
  SIP inspector, call control, media monitor, scenarios
        |
        v
Softphone Engine / Python daemon
  accounts, calls, automation, timeline, expect, plugins
        |
        +-----------------------+
        |                       |
        v                       v
SIP/RTP Stack              Harness Runtime
UAC/UAS, REGISTER, SDP     scenarios, artifacts
RTP, DTMF, media
```

Interfaces can come later:

| Interface | Use |
| --- | --- |
| CLI | CI/CD, scripts, automation. |
| TUI | Interactive technical terminal. |
| GUI/Web | Visual inspector, SIP ladder, media stats. |

## Technical Softphone Capabilities

- Register against Asterisk, PBX, SBC, or trunk.
- Place direct SIP calls.
- Receive direct SIP calls.
- Act as UAC and UAS across transactions.
- Inspect SIP messages in real time.
- Change headers in lab mode.
- Customize SDP in lab mode.
- Pass SIP lab hooks through UAC/UAS config in lab mode.
- Send DTMF through RFC4733, SIP INFO, or in-band when supported.
- Play audio, TTS, silence, tones, noise, or files.
- Receive RTP, record, transcribe, and measure quality.
- Run expectations with `expect()`.
- Export timeline, PCAP, WAV, JSONL, transcript, and HTML/text report.
- Convert manual usage into automation.
- Simulate loss, jitter, delay, unexpected BYE, CANCEL, timeout, and payload errors.

## Technical Softphone CLI

The CLI command is `sipx`. The current root command surface is SIP/RTP-only and curl-like: `options`, `message`, `request`, `register`, `unregister`, `call`, and `listen`.

```bash
sipx register --aor sip:1001@example.com --registrar sip:pbx.example.com:5060 --username 1001 --password "$SIP_PASSWORD"
sipx unregister --aor sip:1001@example.com --registrar sip:pbx.example.com:5060 --username 1001 --password "$SIP_PASSWORD"
sipx call sip:6000@pbx.example.com --aor sip:1001@example.com --registrar sip:pbx.example.com --audio noise --rtp-stats --duration 5
sipx call sip:6000@pbx.example.com --aor sip:1001@example.com --registrar sip:pbx.example.com --rtp-bind 0.0.0.0 --rtp-advertise 203.0.113.10 --jitter-buffer-ms 80 --metrics-json metrics.json
sipx listen --aor sip:1001@example.com --registrar sip:pbx.example.com --local-port 5062 --audio silence --duration 30 --rtp-stats
sipx options sip:pbx.example.com --from sip:1001@example.com -i
sipx message sip:1002@pbx.example.com 'hello' --from sip:1001@example.com
sipx request INFO sip:1002@pbx.example.com --from sip:1001@example.com --username 1001 --password "$SIP_PASSWORD" --debug-sip -H 'Content-Type: application/dtmf-relay' -d 'Signal=1'
```

Root `sipx` intentionally does not expose `scenario`, `profile`, `replay`, or `phone` subcommands.
Implemented account commands fail before network access unless explicit SIP account identity is provided.
Implemented raw SIP request commands support curl-like `-H`, `-d`, `--body-file`, `--include`, and `--no-wait` flags.
Implemented Digest auth retries one `401` or `407` challenge for calls and raw SIP requests when credentials are provided.
Implemented `--debug-sip` prints redacted SIP datagrams without requiring lab mode.
Implemented SIP calls generate SDP audio offers, open RTP, validate `2xx` SDP answers before confirmation, separate RTP bind from advertised SDP address, support synthetic `silence`/`noise` and optional lazy `pyaudio`, and emit call/RTP metrics with `--rtp-stats` or `--metrics-json`.
Implemented `sipx call --dtmf` sends in-dialog SIP INFO `application/dtmf-relay` digits after confirmation.
Implemented LLM examples use `sipx_llm.LLMChatClient` with provider keys supplied only at runtime through `SIPX_LLM_API_KEY`.

## Technical Softphone Python Shape

```python
phone = await h.softphone("lab_account")

await phone.register()

call = await phone.call(
    "sip:ivr@pbx.lab",
    headers={"X-Debug-Session": "abc123"},
)

await expect(call.sip).final_response(200).within(10)
await expect(call.media).to_hear("welcome").within(8)

await call.dtmf.send("1")
await expect(call.media).to_mean("entered the support menu").within(10)
```

Incoming calls:

```python
@phone.on_incoming_call
async def on_call(call: IncomingCall):
    await expect(call.sip).method("INVITE")
    await call.answer(codecs=["PCMU", "PCMA"])

    await call.say("Technical endpoint answering.")
    await call.dtmf.wait("1", timeout=10)
    await call.hangup()
```

## Profiles

Profiles separate realistic endpoint behavior from test behavior.

```toml
[profiles.normal]
mode = "strict"
transport = "udp"
codecs = ["PCMU", "PCMA"]
dtmf = "rfc4733"

[profiles.lab_weird_sdp]
mode = "lab"
transport = "udp"
codecs = ["PCMU"]
allow_custom_sdp = true
allow_malformed_headers = true

[profiles.asterisk_endpoint]
mode = "strict"
registrar = "sip:pbx.lab"
username = "1001"
password = "${SIP_PASSWORD}"
```

Usage:

```python
phone = await h.softphone(profile="lab_weird_sdp")
```

Implemented profile shape uses `harness.toml` tables loaded by `load_profiles()`:

```toml
[profiles.normal]
mode = "strict"
runtime = "sip"

[profiles.normal.account]
aor = "sip:alice@example.com"
registrar = "sip:example.com"
remote_host = "127.0.0.1"
remote_port = 5060

[profiles.lab]
mode = "lab"

[profiles.lab.sip]
headers = { X_Sipx = "yes" }
allow_malformed = true
retransmission_intervals = [0.1, 0.2]

[profiles.lab.media]
codecs = ["PCMU"]
```

## Lab Hooks

Hooks are essential for technical automation.

```python
@phone.hook("before_send_request")
async def add_debug_header(ctx, request):
    request.headers["X-Test-Run"] = ctx.run_id


@phone.hook("after_receive_response")
async def inspect_response(ctx, response):
    ctx.timeline.add("sip.response", status=response.status_code)


@phone.hook("before_sdp_offer")
async def change_sdp(ctx, sdp):
    sdp.audio.codecs.prefer("PCMA")
```

Malformed lab example:

```python
@phone.hook("before_send_request")
async def break_contact_header(ctx, request):
    if request.method == "INVITE":
        request.headers["Contact"] = "<sip:broken@@host>"
```

## Scenario Recorder

The softphone must be able to turn manual testing into an executable scenario.

Flow:

1. Operator starts the softphone.
2. Operator makes a test call.
3. Softphone records SIP, SDP, RTP stats, audio, transcript, and user actions.
4. Operator marks meaningful points such as prompt heard or digit pressed.
5. System exports YAML or Python scenario.
6. Scenario runs later in CI/CD.

Example export:

```yaml
name: recorded_ivr_second_copy
actors:
  caller:
    type: softphone
    account: lab_account

steps:
  - call:
      from: caller
      to: sip:ivr@pbx.lab

  - expect:
      sip.final_response: 200
      within: 10s

  - expect:
      media.hear:
        text: welcome
        mode: semantic
        confidence: 0.8
      within: 8s

  - send_dtmf: "2"

  - expect:
      media.hear:
        text: document number
        mode: contains
      within: 10s
```

Implemented exports are intentionally simple: `ScenarioRecorder.from_timeline()` converts timeline events and user actions into Python or YAML text. Root `sipx` no longer exposes scenario export commands; scenario tooling belongs outside the SIP/RTP-only CLI surface.

## Mixed Scenario

This is a core differentiator.

```python
@scenario("asterisk_routes_to_sip_agent")
async def test_inbound_to_agent(h: Harness):
    caller = h.actor("caller").softphone(runtime="sip")
    agent = h.actor("agent").softphone(runtime="sip", auto_answer=True)
    pbx = h.actor("pbx").asterisk(runtime="asterisk_lab")

    await agent.register()
    await caller.register()

    call = await caller.call("sip:support@pbx.lab")

    await expect(call.sip).final_response(200).within(10)
    await expect(pbx).to_create_bridge().within(3)
    await expect(agent).to_receive_call().within(15)
    await expect(call.media).to_have_two_way_audio()

    await call.hangup()
```

This validates SIP behavior seen by caller, ARI behavior seen by runtime, real media flow, AI/STT/TTS behavior when present, and business flow.

Implemented mixed support starts with `MixedScenario` and `MixedActorSpec`, which bind actors from different registered runtimes onto one shared harness timeline. SIP/Asterisk/media orchestration can build on this binding layer.

## Package Layout

Current workspace layout:

```text
sipx/
  sip/
  sdp/
  rtp/
  media/
  ua.py
apps/
  harness/src/sipx_harness/
  cli/src/sipx_cli/
  asterisk/src/sipx_asterisk/
  llm/src/sipx_llm/
  scenarios/src/sipx_scenarios/
  stt/src/sipx_stt/
  tts/src/sipx_tts/
```

Root import package is `sipx` and contains SIP protocol/runtime surfaces only. Harness concepts import from `sipx_harness`. CLI command is still `sipx`, owned by package `sipx-cli`.

## Security

- Store secrets only in env/config systems, never in scenario artifacts by default.
- Redact `Authorization`, `Proxy-Authorization`, ARI credentials, provider tokens, and SDP crypto lines before logs/artifacts.
- Treat recordings and transcripts as sensitive; recording must be opt-in by scenario/config.
- Use allowlists, CPS limits, and opt-out controls before real outbound calling.
- Prefer TLS/WSS for ARI/WebSocket in production.
- Keep Python as separate process from Asterisk modules unless licensing and maintenance tradeoffs are explicitly accepted.

## Observability Metrics

Minimum metrics:

```text
sip_requests_total{method,status}
sip_transactions_active
sip_retransmissions_total
sip_dialogs_active

rtp_packets_received_total
rtp_packets_lost_total
rtp_packets_late_total
rtp_jitter_ms
rtp_seq_gaps_total
rtp_dtmf_events_total

media_frame_drops_total
media_output_queue_ms
barge_in_total

stt_partial_latency_ms
stt_final_latency_ms
tts_first_audio_ms
agent_response_ms

calls_active
calls_completed_total
calls_failed_total
call_duration_seconds
```

Every call should have a trace identity that links SIP Call-ID, local/remote tags, local/remote SSRC, RTP port, scenario ID, recording ID, agent session ID, and Asterisk channel/bridge IDs when available.

## Testing Strategy

- Unit tests first for core timeline, expectations, verdicts, artifacts, capabilities.
- Mock runtime tests for scenario runner without network.
- Asterisk integration tests behind explicit environment/config.
- SIP parser and RTP parser tests with fuzz/property coverage.
- Semantic AI assertions separated from deterministic protocol assertions.
- Parser tests for valid messages, compact headers, multiline headers, body with Content-Length.
- Transaction tests for timers, retransmission, timeout, CANCEL, ACK.
- Dialog tests for CSeq, tags, route set, BYE.
- SDP tests for dynamic payloads, direction, fmtp, telephone-event.
- RTP tests for parse/serialize, sequence rollover, timestamp.
- DTMF tests for start, repetition, end bit, duration.
- Jitter tests for loss, reorder, delay, burst loss.
- IVR tests for timeout, interdigit, barge-in, fallback.

Interop matrix:

```text
sipx UAC  -> Asterisk / FreeSWITCH / Kamailio / SIP trunk
sipx UAS  <- Asterisk / FreeSWITCH / SIPp / custom client
sipx RTP  <-> RTP proxy / packet capture / impairment simulator
```

## Roadmap

Priority rule: do not start with a complete AI bot. Start with testability and timeline.

1. Harness core: Actor, Scenario, Expect, Timeline, Artifact, Verdict, Metrics.
2. MockRuntime and CLI skeleton.
3. AsteriskRuntime via ARI/Stasis.
4. One Asterisk media path.
5. STT/TTS app protocols and media frame pipeline.
6. SipUserAgent minimum.
7. Technical softphone headless.
8. Scenario recorder/exporter and replay.
9. Reports.
10. Advanced SIP lab, fuzzing, conformance, interop.

## Phase 1 - Harness Core

Tasks:

- `Actor`.
- `Scenario`.
- `Expect`.
- `Timeline`.
- `Artifact`.
- `Verdict`.
- `Metrics`.
- Runtime capability model.
- Rich failure format.
- CLI skeleton.

## Phase 2 - AsteriskRuntime MVP

Tasks:

- Async ARI REST client.
- ARI WebSocket event consumer.
- Stasis app handling.
- Originate.
- Answer.
- Hangup.
- Playback.
- DTMF send/receive.
- Bridge creation.
- Recording.
- Timeline ARI mapping.
- Minimal Asterisk config examples.

## Phase 3 - Media And AI Runtime

Tasks:

- `AudioFrame`.
- `MediaPort`.
- STT protocol in `sipx_stt`.
- TTS protocol in `sipx_tts`.
- Transcript events.
- Barge-in policy.
- Silence/placeholder behavior when AI is slow.
- DTMF event model.
- Recording/transcript artifacts.

## Phase 4 - SipUserAgent Minimum

SIP tasks:

- UDP transport runtime.
- Parser/serializer.
- INVITE client/server.
- 100/180/183/200/4xx/5xx.
- ACK.
- BYE.
- CANCEL.
- REGISTER client.
- Basic Digest auth.
- Dialogs.
- Transaction timers.

SDP tasks:

- Audio media.
- PCMU/PCMA.
- Telephone-event.
- `sendrecv/sendonly/recvonly/inactive`.

RTP tasks:

- PCMU/PCMA.
- RTP packetizer/depacketizer.
- Simple jitter buffer.
- DTMF RFC4733.
- WAV recording.
- Basic stats.

Harness tasks:

- Timeline events for SIP/SDP/RTP/DTMF.
- Expectations for SIP/SDP/RTP/media.
- Artifacts.

## Phase 5 - Technical Softphone Headless

Tasks:

- Accounts.
- Profiles.
- Register/unregister.
- Manual call via CLI.
- Receive calls.
- Live SIP inspector.
- Recording.
- Transcript.
- Scenario export.
- Replay.
- Lab hooks.
- Strict and lab modes.

## Phase 6 - Reports And Evidence

Tasks:

- `timeline.jsonl`.
- `sip_messages.txt`.
- `recording.wav`.
- `transcript.json`.
- `pcap.pcapng` when available.
- `report.html`.
- `report.txt`.

Implemented report behavior writes `timeline.jsonl`, `verdict.json`, `report.txt`, and `report.html` for each scenario run. Recording, transcript, and PCAP artifacts remain optional future evidence paths.

## Phase 7 - Advanced SIP Lab

Tasks:

- Malformed mode.
- re-INVITE.
- UPDATE.
- REFER.
- PRACK.
- Session timers.
- TCP/TLS.
- SRTP.
- SIP over WebSocket.
- Media impairment.
- Fuzzing CI.
- Conformance suites.

## Phase 8 - Optional UI And Optional Runtimes

UI features:

- Account list.
- Active calls.
- SIP ladder.
- SDP viewer.
- RTP stats.
- Audio/transcript panel.
- Expect panel.
- Timeline viewer.
- Export scenario button.

Optional runtimes:

- `PjsipRuntime` for robust softphone interop.
- `SippRuntime` for load/conformance workflows.
- External SBC/proxy integrations when required.

`PjsipRuntime` tradeoffs:

- Use it when robust softphone interoperability, mature NAT behavior, TLS/SRTP, or production endpoint compatibility matter more than malformed wire control.
- Do not use it as the core protocol-lab runtime because PJSIP normalizes messages and is not designed to emit arbitrary malformed SIP/SDP/RTP.
- Keep it optional so the SIP UAC/UAS runtime remains the source for strict/lab wire-level tests and technical-softphone fault injection.
- Prefer adding `PjsipRuntime` after profile config, SIP lab hooks, and Asterisk integration are stable.

## Asterisk Docker Lab

`docker/asterisk` provides a local Asterisk 22 lab with ARI, PJSIP, RTP ports, simple UAS extensions, and a Stasis target. Tests in `apps/asterisk/tests/test_asterisk_integration.py` are skipped by default and run only with `SIPX_ASTERISK_INTEGRATION=1`.

## Validation Gates

Standard local checks:

```bash
ruff format --check .
ruff check .
uv run ty check
pytest
```

Protocol work adds parser fuzz/property tests, golden round-trip tests, timer tests, and synthetic RTP impairment tests.

Asterisk work adds mocked ARI tests and optional integration tests behind explicit env/config. No secret-dependent CI by default.
