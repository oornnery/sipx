# sipx - Examples

## No network required

| Example | Description |
|---------|-------------|
| `sdp.py` | SDP creation, offer/answer, codec analysis |
| `audio.py` | Tone, silence, noise, DTMF tone generators |
| `parser.py` | Parse raw SIP messages, headers, URIs |

```bash
uv run python examples/sdp.py
uv run python examples/audio.py
uv run python examples/parser.py
```

## Requires Asterisk (`docker-compose up -d`)

| Example | Description |
|---------|-------------|
| `quickstart.py` | One-liner examples: register, options, call, message |
| `call.py` | Complete call: REGISTER → INVITE → ACK → BYE |
| `events.py` | All event handler patterns (@on decorator) |
| `dtmf.py` | 3 DTMF methods: RFC 4733, SIP INFO, inband |
| `asterisk.py` | Comprehensive test of every library component |

```bash
cd docker/asterisk && docker-compose up -d
uv run python examples/quickstart.py
uv run python examples/call.py
uv run python examples/events.py
uv run python examples/dtmf.py
uv run python examples/asterisk.py
```

## No Asterisk (sipx as server + client)

| Example | Description |
|---------|-------------|
| `server.py` | SIP server with decorators + DI extractors |
| `ivr.py` | Async IVR with real RTP + DTMF (3 methods) |

```bash
uv run python examples/server.py   # then test from another terminal
uv run python examples/ivr.py           # self-contained client+server
```

See [docs/SDD.md](../docs/SDD.md) for the full spec.
