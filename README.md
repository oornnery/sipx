# sipx

`sipx` is a Python SIP protocol library: an httpx-style async client, sans-I/O
SIP/SDP/RTP primitives, and media helpers. Use it to send REGISTER, OPTIONS,
MESSAGE, INVITE, SUBSCRIBE, and arbitrary SIP methods against any cooperative
peer, with Digest authentication, dialog tracking, and UDP/TCP/TLS transports.

Requires Python `>=3.14`.

## Install

From the repository root (editable workspace install):

```bash
uv sync
```

Or install the published package when available:

```bash
pip install sipx
```

## Quick start

```python
import asyncio
from sipx import AsyncClient, AuthDigest, Settings

settings = Settings(
    from_uri="sip:1001@example.com",
    timeout=10.0,
)
auth = AuthDigest(username="1001", password="secret")

async def main() -> None:
    async with AsyncClient(settings=settings, auth=auth) as client:
        response = await client.register("sip:pbx.example.com:5060")
        print(response.status_code, response.reason)

asyncio.run(main())
```

## AsyncClient

`AsyncClient` is the main runtime. One client, one `Settings`, optional
`AuthDigest`, and optional `event_hooks`.

### UAC methods

| Method | RFC | Purpose |
| --- | --- | --- |
| `register(uri, **headers)` | 3261 | REGISTER / unregister (`Expires: 0`) |
| `options(uri)` | 3261 §11 | Capability probe |
| `message(uri, body, **headers)` | 3428 | SIP MESSAGE |
| `invite(uri, **kwargs)` | 3261 §13 | Start a session |
| `subscribe(uri, **headers)` | 3265 | Event subscription |
| `request(method, uri, **kwargs)` | — | Any SIP method (INFO, NOTIFY, …) |
| `ack(call_id)` | 3261 §13.2.2.4 | Confirm a 2xx INVITE |
| `bye(call_id)` | 3261 §15 | Terminate a dialog |
| `cancel(call_id)` | 3261 §9 | Abort a pending INVITE |

### UAS handlers

Register inbound handlers with decorators; deliver requests with
`handle_request()`:

```python
from sipx import AsyncClient, Response

client = AsyncClient()

@client.on_options
async def handle_options(request) -> Response:
    return Response(
        status_code=200,
        reason="OK",
        headers={"Allow": "INVITE, ACK, BYE, OPTIONS, MESSAGE"},
        request=request,
    )

# In your receive loop:
# response = await client.handle_request(inbound_request)
```

### Responses and `history`

Every UAC call returns one final `Response` (the first `>= 200`). Provisional
`1xx` replies and `401`/`407` Digest challenges are collected on
`response.history` in arrival order, each with its own `.request`:

```python
response = await client.invite("sip:6000@pbx.example.com")
for item in response.history:
    print(item.status_code, item.reason)
print(response.status_code)  # final
```

### Event hooks

Hooks follow the httpx pattern — a dict of event name to list of callables
(sync or async, side-effect only):

```python
def log_request(request) -> None:
    print(f"> {request.method} {request.uri}")

def log_response(response) -> None:
    print(f"< {response.status_code}")

client = AsyncClient(
    event_hooks={"request": [log_request], "response": [log_response]},
)
```

### CANCEL a ringing INVITE

`invite()` blocks until the final response. To abort a still-ringing call, run
the INVITE in one task and `cancel()` from another. Pass an explicit `Call-ID`
so the cancel task knows what to target:

```python
import asyncio

async with AsyncClient(settings=settings, auth=auth) as client:
    call_id = "demo-call-1"
    invite = asyncio.create_task(
        client.invite("sip:6000@pbx.example.com", **{"Call-ID": call_id})
    )
    await asyncio.sleep(1)
    await client.cancel(call_id)   # 200 OK to CANCEL
    response = await invite        # 487 Request Terminated
```

### Settings

```python
from sipx import Settings

settings = Settings(
    from_uri="sip:1001@example.com",
    contact_uri="sip:1001@192.168.1.10:5060",
    local_host="0.0.0.0",
    local_port=0,          # 0 = ephemeral
    timeout=10.0,
    rport=True,            # RFC 3581; add ;rport to UDP Via
    retransmit=True,       # RFC 3261 §17 UDP retransmission
    user_agent="my-app/1.0",
)
```

`AsyncClient.learned_address` exposes the public `(host, port)` learned from
`received`/`rport` parameters echoed on response Via headers.

## RFC behavior

`AsyncClient` correlates replies by `Call-ID`, CSeq number/method, top Via
`branch`, and destination port. For hostname targets the source IP is accepted
(the datagram arrives from the resolved address); for IP-literal targets the
source host must match.

Implemented client behavior:

- **UDP retransmission (§17).** T1/T2 backoff until reply or `timeout`; INVITE
  stops after the first provisional; TCP/TLS never retransmit.
- **Non-2xx INVITE ACK (§17.1.1.3).** Auto-ACK on 3xx–6xx finals.
- **CANCEL (§9).** `cancel(call_id)` for a pending INVITE.
- **rport (RFC 3581).** Outgoing UDP Via carries `;rport`; toggle with
  `Settings.rport`.
- **PRACK / 100rel (RFC 3262).** Reliable provisionals (RSeq + `100rel`) are
  auto-PRACKed with `RAck`.
- **Digest (RFC 7616/8760).** `AuthDigest` supports MD5, MD5-sess, SHA-256,
  SHA-256-sess; one challenge retry per request.
- **Dialog tags (§12.2.2).** UAC dialogs reject conflicting From/To tags.
- **Content-Length.** Added on every outbound `Request.to_bytes()` (needed for
  TCP/TLS framing).

Inbound requests are not auto-routed: the receive loop dispatches responses to
in-flight calls; call `handle_request()` yourself to reach `on_*` handlers.

Standalone extension handlers under `sipx/extensions/` (PRACK, DNS, events,
presence, outbound) are test-only and not wired into `AsyncClient`.

## Core modules

| Module | Contents |
| --- | --- |
| `sipx.client` | `AsyncClient`, transports, response correlation |
| `sipx.models` | `Request`, `Response` dataclasses |
| `sipx.config` | `Settings` |
| `sipx.protocol` | Transactions, dialog, `AuthDigest`, event hooks |
| `sipx.transport` | UDP, TCP, TLS, registry |
| `sipx.sip` | Sans-I/O parser, serializer, URI, Digest helpers |
| `sipx.sdp` | Session description, offer/answer (PCMU, PCMA, telephone-event) |
| `sipx.rtp` | Packet parse/serialize, G.711, RFC4733 DTMF, jitter buffer, `RtpAudioSession` |
| `sipx.media` | `AudioFrame`, synthetic `silence`/`noise` sources, optional PyAudio |

Root exports include `AsyncClient`, `AuthDigest`, `Settings`, `Request`,
`Response`, `EventHooks`, and the SIP/SDP/RTP types above.

## Examples

Runnable scripts under `sipx.examples` use only the core package. Run from the
repository root with `uv run`. They default to the public Mizu demo account but
read generic `SIPX_*` env vars so the same code targets any SIP provider:

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

Set `SIPX_DEBUG=1` to print SIP wire to stderr, for example
`SIPX_DEBUG=1 uv run python -m sipx.examples.options`.

| Example | Needs live peer | Notes |
| --- | --- | --- |
| `register`, `unregister` | yes | `SIPX_EXPIRES` |
| `options`, `message` | yes | `SIPX_MESSAGE`, `SIPX_CONTENT_TYPE` |
| `subscribe` | yes | `SIPX_EVENT`, `SIPX_ACCEPT` |
| `invite`, `call` | yes | `SIPX_CODECS`, `SIPX_RTP_PORT` |
| `cancel` | yes | `SIPX_CANCEL_AFTER` (seconds before CANCEL) |
| `info_dtmf`, `hooks_history` | yes | in-dialog INFO / event hooks demo |
| `server` | no | offline UAS via `handle_request` |

## Development

```bash
ruff format --check .
ruff check .
uv run ty check
uv run pytest
```

Core tests live under `tests/`. See `SPEC.md`, `DESIGN.md`, and `CHANGELOG.md`
for implementation detail and version history.

## Security

- Redact `Authorization` and `Proxy-Authorization` before logging SIP wire.
- Redact SDP `a=crypto` lines in artifacts and debug output.
- Do not commit real account passwords or provider API keys.
- Use TLS (`transport="tls"`) for SIP over untrusted networks.
- Obtain consent and respect CPS limits before placing outbound calls.
