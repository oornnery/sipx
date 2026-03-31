# sipx - Examples

## No network required

| Example | Description |
|---------|-------------|
| `sdp_demo.py` | SDP creation, offer/answer, codec analysis |
| `audio_gen.py` | Tone, silence, noise, DTMF tone generators |
| `parser_demo.py` | Parse raw SIP messages, headers, URIs |

```bash
uv run python examples/sdp_demo.py
uv run python examples/audio_gen.py
uv run python examples/parser_demo.py
```

## Requires Asterisk (`docker-compose up -d`)

| Example | Description |
|---------|-------------|
| `quickstart.py` | One-liner examples: register, options, call, message |
| `call_flow.py` | Complete call: REGISTER → INVITE → ACK → BYE |
| `events_demo.py` | All event handler patterns (@on decorator) |
| `dtmf_demo.py` | 3 DTMF methods: RFC 4733, SIP INFO, inband |
| `asterisk_full.py` | Comprehensive test of every library component |

```bash
cd docker/asterisk && docker-compose up -d
uv run python examples/quickstart.py
uv run python examples/call_flow.py
uv run python examples/events_demo.py
uv run python examples/dtmf_demo.py
uv run python examples/asterisk_full.py
```

## No Asterisk (sipx as server + client)

| Example | Description |
|---------|-------------|
| `server_demo.py` | SIP server with decorators + DI extractors |
| `ivr.py` | Async IVR with real RTP + DTMF (3 methods) |

```bash
uv run python examples/server_demo.py   # then test from another terminal
uv run python examples/ivr.py           # self-contained client+server
```

See [docs/SDD.md](../docs/SDD.md) for the full spec.
