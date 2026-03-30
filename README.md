# sipx

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A modern, high-performance SIP library for Python inspired by [httpx](https://www.python-httpx.org/).

Build voice automation scripts, IVR systems, AI-powered call handlers, and SIP testing tools with a clean, Pythonic API.

## Features

- **httpx-inspired API** — `client.invite()`, `client.register()`, sync and async
- **Declarative events** — `@event_handler('INVITE', status=200)` decorators
- **Full SIP support** — 14 methods: INVITE, REGISTER, BYE, ACK, CANCEL, OPTIONS, MESSAGE, SUBSCRIBE, NOTIFY, REFER, INFO, UPDATE, PRACK, PUBLISH
- **Digest authentication** — MD5, SHA-256, automatic challenge parsing, manual retry control
- **SDP offer/answer** — RFC 4566 compliant, codec negotiation, media analysis
- **Multiple transports** — UDP, TCP, TLS (sync + async)
- **State management** — Transaction FSMs (ICT/NICT) and Dialog tracking per RFC 3261
- **Extensible** — ABC-based transports, body parsers, auth methods

## Quick Start

```python
from sipx import Client, Events, Auth, event_handler, SDPBody

class MyEvents(Events):
    @event_handler('INVITE', status=200)
    def on_call_accepted(self, request, response, context):
        print(f"Call accepted! SDP: {response.body}")

    @event_handler('INVITE', status=180)
    def on_ringing(self, request, response, context):
        print("Ringing...")

with Client() as client:
    client.events = MyEvents()
    client.auth = Auth.Digest('alice', 'secret')

    # Register
    response = client.register('sip:alice@pbx.example.com')
    if response.status_code == 401:
        response = client.retry_with_auth(response)

    # Make a call
    sdp = SDPBody.create_offer(
        session_name="Call",
        origin_username="alice",
        origin_address="192.168.1.100",
        connection_address="192.168.1.100",
        media_specs=[{
            "media": "audio",
            "port": 8000,
            "codecs": [
                {"payload": "0", "name": "PCMU", "rate": "8000"},
                {"payload": "8", "name": "PCMA", "rate": "8000"},
            ],
        }],
    )
    response = client.invite('sip:bob@pbx.example.com', body=sdp.to_string())
    if response.status_code == 401:
        response = client.retry_with_auth(response)
    if response.status_code == 200:
        client.ack(response=response)
        # call is active...
        client.bye(response=response)
```

## Installation

```bash
# With uv (recommended)
uv add sipx

# With pip
pip install sipx

# From source
git clone https://github.com/yourusername/sipx.git
cd sipx
uv sync
```

**Requires Python 3.13+**

## Usage Examples

### Registration

```python
from sipx import Client, Auth

with Client(local_port=5061) as client:
    client.auth = Auth.Digest('alice', 'secret')
    response = client.register('sip:alice@pbx.example.com')
    if response.status_code == 401:
        response = client.retry_with_auth(response)
    print(f"Status: {response.status_code}")  # 200
```

### Send Message

```python
with Client() as client:
    response = client.message(
        to_uri='sip:bob@example.com',
        content='Hello from sipx!'
    )
```

### Check Server Capabilities

```python
with Client() as client:
    response = client.options('sip:pbx.example.com')
    print(response.headers.get('Allow'))
```

### Async Client

```python
import asyncio
from sipx import AsyncClient, Auth

async def main():
    async with AsyncClient(local_port=5061) as client:
        client.auth = Auth.Digest('alice', 'secret')
        response = await client.register('sip:alice@pbx.example.com')
        if response.status_code == 401:
            response = await client.retry_with_auth(response)

asyncio.run(main())
```

### Event Handlers

```python
from sipx import Events, event_handler

class CallEvents(Events):
    def on_request(self, request, context):
        print(f"Sending {request.method}")
        return request

    def on_response(self, response, context):
        print(f"Received {response.status_code}")
        return response

    @event_handler('INVITE', status=200)
    def on_call_ok(self, request, response, context):
        print("Call accepted!")

    @event_handler(status=(401, 407))
    def on_auth(self, request, response, context):
        print("Auth required")

    @event_handler('INVITE', status=183)
    def on_early_media(self, request, response, context):
        if response.body and response.body.has_early_media():
            print("Early media detected")
```

### Transport Selection

```python
# UDP (default)
client = Client(transport="UDP")

# TCP (reliable, large messages)
client = Client(transport="TCP")

# TLS (encrypted, SIPS)
client = Client(transport="TLS")
```

## Authentication

sipx uses **explicit authentication** — you control when to retry:

```python
client.auth = Auth.Digest('alice', 'secret')

response = client.register('sip:alice@pbx.example.com')
if response.status_code in (401, 407):
    response = client.retry_with_auth(response)
```

This gives full control over the auth flow. You can use different credentials per request:

```python
response = client.invite('sip:bob@example.com')
if response.status_code == 401:
    custom_auth = Auth.Digest('alice', 'different_password')
    response = client.retry_with_auth(response, auth=custom_auth)
```

## Supported Methods

| Method | Description | Example |
|--------|-------------|---------|
| INVITE | Establish a call | `client.invite('sip:bob@ex.com', body=sdp)` |
| ACK | Acknowledge INVITE | `client.ack(response=r)` |
| BYE | Terminate a call | `client.bye(response=r)` |
| CANCEL | Cancel pending INVITE | `client.cancel(response=r)` |
| REGISTER | Register location | `client.register('sip:alice@ex.com')` |
| OPTIONS | Query capabilities | `client.options('sip:ex.com')` |
| MESSAGE | Instant message | `client.message('sip:bob@ex.com', content='Hi')` |
| SUBSCRIBE | Subscribe to events | `client.subscribe('sip:bob@ex.com')` |
| NOTIFY | Event notification | `client.notify('sip:bob@ex.com')` |
| REFER | Call transfer | `client.refer('sip:bob@ex.com', refer_to='sip:carol@ex.com')` |
| INFO | Mid-dialog info (DTMF) | `client.info('sip:bob@ex.com', content=dtmf)` |
| UPDATE | Update session | `client.update('sip:bob@ex.com', sdp_content=sdp)` |
| PRACK | Provisional ACK | `client.prack(response=r)` |
| PUBLISH | Publish state | `client.publish('sip:bob@ex.com')` |

## RFC Compliance

| RFC | Title | Status |
|-----|-------|--------|
| 3261 | SIP: Session Initiation Protocol | Core implemented |
| 2617 | HTTP Digest Authentication | Complete |
| 7616 | HTTP Digest (SHA-256) | Complete |
| 4566 | SDP: Session Description Protocol | Complete |
| 3264 | Offer/Answer Model with SDP | Complete |

## Documentation

| Document | Description |
|----------|-------------|
| [docs/SDD.md](docs/SDD.md) | Software Design Document (full spec, diagrams, roadmap) |
| [docs/QUICK_START.md](docs/QUICK_START.md) | Quick start guide |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Architecture overview |
| [docs/MODULES.md](docs/MODULES.md) | Module reference |
| [examples/](examples/) | Working examples |
| [docker/asterisk/](docker/asterisk/) | Asterisk test environment |

## Testing with Asterisk

```bash
cd docker/asterisk
docker-compose up -d
uv run python examples/asterisk_demo.py
```

## Roadmap

See [docs/SDD.md](docs/SDD.md) for the full roadmap. Key upcoming work:

- **RTP engine** — send/receive audio (RFC 3550)
- **DTMF** — RFC 4733 (RTP) + SIP INFO
- **Codecs** — G.711 (PCMU/PCMA), Opus
- **TTS/STT adapters** — for AI-powered voice automation
- **IVR builder** — menus, prompts, DTMF collection
- **WebSocket transport** — RFC 7118
- **Native async** — replace sync wrapper with true async

## Development

```bash
git clone https://github.com/yourusername/sipx.git
cd sipx
uv sync
uv run ruff check sipx
uv run pytest
```

## Inspirations

**API design:**
- [httpx](https://www.python-httpx.org/) — Pythonic API, sync/async, extensible

**Reference implementations (studied for patterns and ideas):**
- [sipd](https://github.com/initbar/sipd) — SIP daemon implementation
- [sipmessage](https://github.com/spacinov/sipmessage) — SIP message parsing
- [sip-parser](https://github.com/alxgb/sip-parser) — SIP parser
- [PySipIvr](https://github.com/ersansrck/PySipIvr) — SIP IVR implementation
- [sip-resources](https://github.com/miconda/sip-resources) — Curated SIP resources and documentation

**Other inspirations:**
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
