# sipx

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A modern, high-performance SIP library for Python inspired by [httpx](https://www.python-httpx.org/).

Build voice automation scripts, IVR systems, AI-powered call handlers, and SIP testing tools with a clean, Pythonic API.

## Features

- **httpx-inspired API** — `client.invite()`, `client.register()`, sync and async
- **FastAPI-style server** — `@server.invite`, `Annotated` DI extractors
- **Response builders** — `request.ok()`, `request.trying()`, `request.error(code)`
- **Dialog tracking** — `client.ack()` / `client.bye()` without passing response
- **Declarative events** — `@on('INVITE', status=200)` decorators
- **Full SIP support** — 14 methods, auto 100 Trying, auto DNS SRV resolution
- **Digest authentication** — MD5, SHA-256, auto-retry on 401/407
- **RTP + DTMF** — RFC 4733 + SIP INFO + Inband, sync and async
- **SDP with ICE/SRTP** — RFC 4566, offer/answer, ICE candidates, DTLS
- **Media pipeline** — RTP, tone generators, TTS/STT adapters, IVR builder
- **SIP-I** — Real ISUP binary encoding (ITU-T Q.763), Brazilian SIP-I (ANATEL)
- **Multiple transports** — UDP, TCP, TLS, WebSocket (sync + async)
- **State management** — Transaction FSMs with Timer A/E retransmission
- **Extensible** — ABC-based transports, body parsers, custom DI extractors

## Quick Start

```python
import sipx

# One-liners
sipx.options("sip:pbx.example.com")
sipx.register("sip:alice@pbx.com", auth=("alice", "secret"))
sipx.send("sip:bob@pbx.com", "Hello!", auth=("alice", "secret"))

# Full call with dialog tracking
from sipx import Client

with Client(local_port=5061) as client:
    client.auth = ("alice", "secret")

    client.register("sip:alice@pbx.com")

    sdp = client.create_sdp(port=8000)
    r = client.invite("sip:bob@pbx.com", body=sdp.to_string())

    if r.status_code == 200:
        client.ack()    # uses tracked dialog
        # call is active...
        client.bye()    # uses tracked dialog
```

## Installation

```bash
# With uv (recommended)
uv add sipx

# With pip
pip install sipx

# From source
git clone https://github.com/oornnery/sipx.git
cd sipx
uv sync
```

### Requirements

Python 3.12+

## Usage Examples

### SIP Server (FastAPI-style decorators + DI)

```python
from typing import Annotated
from sipx import SIPServer, Request, FromHeader, Header

server = SIPServer(local_host="127.0.0.1", local_port=5060)

@server.register
def on_register(request: Request, caller: Annotated[str, FromHeader]):
    print(f"REGISTER from {caller}")
    return request.ok()

@server.message
def on_message(request: Request, caller: Annotated[str, FromHeader]):
    body = request.content.decode() if request.content else ""
    print(f"MESSAGE from {caller}: {body}")
    return request.ok()

server.start()
```

### Async Client

```python
import asyncio
from sipx import AsyncClient

async def main():
    async with AsyncClient(local_port=5061) as client:
        client.auth = ("alice", "secret")

        r = await client.register("sip:alice@pbx.com")
        print(f"REGISTER: {r.status_code}")

        sdp = client.create_sdp(port=8000)
        r = await client.invite("sip:bob@pbx.com", body=sdp.to_string())
        if r and r.status_code == 200:
            await client.ack()
            await asyncio.sleep(5)
            await client.bye()

asyncio.run(main())
```

### FastAPI + SIP Integration

Run a REST API that controls SIP operations:

```bash
# Terminal 1: SIP server
uv run python examples/server.py

# Terminal 2: FastAPI
uv run python examples/fastapi_sip.py

# Terminal 3: test via curl
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"uri":"sip:test@127.0.0.1:15090","content":"Hello from FastAPI!"}' | jq
```

```json
{
  "status_code": 200,
  "reason": "OK"
}
```

Full request/response trace with retransmission timers, DI resolution, and FSM state transitions:

```text
# FastAPI (client side)
INFO     UDP bound to 0.0.0.0:40703
DEBUG    Transaction 592b5fee created: MESSAGE (type=NON_INVITE)
DEBUG    Timer E started (0.5s)          # retransmission armed
DEBUG    Timer F started (32.0s)         # timeout armed
DEBUG    UDP send 335 bytes -> 127.0.0.1:15090
DEBUG    UDP recv 245 bytes <- 127.0.0.1:15090
DEBUG    <<< 200 OK
DEBUG    Transaction 592b5fee: TRYING -> COMPLETED
DEBUG    Timer E cancelled               # retransmission stopped
DEBUG    Timer F cancelled               # timeout stopped

# SIP Server (server side)
DEBUG    UDP recv 335 bytes <- 127.0.0.1:40703
DEBUG    Resolving handler on_message
DEBUG    Extracting caller via FromHeader()
  MESSAGE from <sip:user@0.0.0.0>: Hello from FastAPI!
DEBUG    >>> SENDING 200 OK to 127.0.0.1:40703
DEBUG    UDP send 245 bytes -> 127.0.0.1:40703
```

### Event Handlers

```python
from sipx import Events, on

class CallEvents(Events):
    @on('INVITE', status=200)
    def on_call_ok(self, request, response, context):
        print("Call accepted!")

    @on('INVITE', status=(180, 183))
    def on_ringing(self, request, response, context):
        print(f"Ringing... ({response.status_code})")

    @on(status=(401, 407))
    def on_auth(self, request, response, context):
        print("Auth challenge received")
```

### Authentication

```python
# Tuple auth (auto-retry on 401/407)
client.auth = ("alice", "secret")

# Or explicit Auth object
client.auth = Auth.Digest("alice", "secret")

# Per-request override
r = client.register("sip:alice@pbx.com")
if r.status_code == 401:
    r = client.retry_with_auth(r, auth=Auth.Digest("alice", "other"))
```

## Supported Methods

| Method    | Description            | Example                                                       |
| --------- | ---------------------- | ------------------------------------------------------------- |
| INVITE    | Establish a call       | `client.invite('sip:bob@ex.com', body=sdp)`                   |
| ACK       | Acknowledge INVITE     | `client.ack()` (auto dialog)                                  |
| BYE       | Terminate a call       | `client.bye()` (auto dialog)                                  |
| CANCEL    | Cancel pending INVITE  | `client.cancel(response=r)`                                   |
| REGISTER  | Register location      | `client.register('sip:alice@ex.com')`                         |
| OPTIONS   | Query capabilities     | `client.options('sip:ex.com')`                                |
| MESSAGE   | Instant message        | `client.message('sip:bob@ex.com', content='Hi')`              |
| SUBSCRIBE | Subscribe to events    | `client.subscribe('sip:bob@ex.com')`                          |
| NOTIFY    | Event notification     | `client.notify('sip:bob@ex.com')`                             |
| REFER     | Call transfer          | `client.refer('sip:bob@ex.com', refer_to='sip:carol@ex.com')` |
| INFO      | Mid-dialog info (DTMF) | `client.info('sip:bob@ex.com', content=dtmf)`                 |
| UPDATE    | Update session         | `client.update('sip:bob@ex.com', sdp_content=sdp)`            |
| PRACK     | Provisional ACK        | `client.prack(response=r)`                                    |
| PUBLISH   | Publish state          | `client.publish('sip:bob@ex.com')`                            |

## RFC Compliance

| RFC  | Title                             | Status                                     |
| ---- | --------------------------------- | ------------------------------------------ |
| 3261 | SIP: Session Initiation Protocol  | Complete (auto 100 Trying, retransmission) |
| 2617 | HTTP Digest Authentication        | Complete (MD5, SHA-256)                    |
| 7616 | HTTP Digest (SHA-256)             | Complete                                   |
| 4566 | SDP: Session Description Protocol | Complete (ICE, SRTP, DTLS)                 |
| 3264 | Offer/Answer Model with SDP       | Complete                                   |
| 3550 | RTP: Real-time Transport Protocol | Complete (sync + async)                    |
| 4733 | DTMF via RTP (telephone-event)    | Complete                                   |
| 3263 | DNS SRV Resolution                | Complete (auto in Client)                  |
| 4028 | Session Timers                    | Complete                                   |

## Documentation

| Document                                 | Description                                             |
| ---------------------------------------- | ------------------------------------------------------- |
| [docs/SDD.md](docs/SDD.md)               | Software Design Document (full spec, diagrams, roadmap) |
| [examples/README.md](examples/README.md) | Examples catalog (22 examples)                          |
| [docker/asterisk/](docker/asterisk/)     | Asterisk test environment                               |

## Testing with Asterisk

```bash
cd docker/asterisk
docker-compose up -d
uv run python examples/asterisk.py
```

## Examples

See [examples/README.md](examples/README.md) for the full list. Highlights:

| Example                                               | What it shows                            |
| ----------------------------------------------------- | ---------------------------------------- |
| [quickstart.py](examples/quickstart.py)               | One-liner register, options, call, send  |
| [call.py](examples/call.py)                           | REGISTER -> INVITE -> ACK -> BYE         |
| [server.py](examples/server.py)                       | SIPServer with decorators + DI           |
| [ivr.py](examples/ivr.py)                             | Async IVR with RTP + DTMF                |
| [response_builders.py](examples/response_builders.py) | request.ok/trying/error, dialog tracking |
| [asterisk.py](examples/asterisk.py)                   | Comprehensive integration test           |

## Roadmap

See [docs/SDD.md](docs/SDD.md) for the full roadmap. Key upcoming work:

- **SRTP** — packet encryption (RFC 3711)
- **RTCP** — control protocol (RFC 3550 Section 6)
- **Jitter buffer** — for smooth RTP playback
- **Coverage >80%** — currently 607 tests, ~60%
- **PyPI publishing** — package ready, CI pipeline configured

## Development

```bash
git clone https://github.com/oornnery/sipx.git
cd sipx
uv sync
uv run ruff check sipx
uv run pytest
```

## Inspirations

API design:

- [httpx](https://www.python-httpx.org/) — Pythonic API, sync/async, extensible

Reference implementations:

- [sipd](https://github.com/initbar/sipd) — SIP daemon implementation
- [sipmessage](https://github.com/spacinov/sipmessage) — SIP message parsing
- [sip-parser](https://github.com/alxgb/sip-parser) — SIP parser
- [PySipIvr](https://github.com/ersansrck/PySipIvr) — SIP IVR implementation
- [sip-resources](https://github.com/miconda/sip-resources) — Curated SIP resources and documentation

Other inspirations:

- [pyVoIP](https://github.com/tayler6000/pyVoIP) — VoIP functionality
- [aiosip](https://github.com/Eyepea/aiosip) — Async SIP
- [b2bua](https://github.com/sippy/b2bua) — Back-to-back user agent
- [pysipp](https://github.com/SIPp/pysipp) — SIP testing
- [PySIPio](https://pypi.org/project/PySIPio/) — SIP I/O
- [katariSIP](https://github.com/klocation/katarisip) — SIP library
- [SIP-Auth-helper](https://github.com/pbertera/SIP-Auth-helper) — SIP auth tools
- [callsip.py](https://github.com/rundekugel/callsip.py) — Simple SIP caller

## License

MIT License
