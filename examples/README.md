# sipx - Examples

## Offline (no network required)

| Example | Features | Description |
| --- | --- | --- |
| `parser.py` | MessageParser, Headers, SipURI | Parse raw SIP messages, headers, URIs |
| `sdp.py` | SDPBody, offer/answer, codecs | SDP creation, codec negotiation |
| `audio.py` | ToneGenerator, DTMFToneGenerator | Sine waves, silence, noise, DTMF tones |
| `ivr_menu.py` | Menu, MenuItem, Prompt | IVR menu builder patterns |
| `response_builders.py` | request.ok/trying/error, create_sdp | Response builder methods + dialog tracking |
| `dialog_tracking.py` | StateManager, Transaction, Dialog | FSM transaction and dialog lifecycle |
| `routing.py` | RouteSet, Record-Route | Route set extraction and application |

```bash
uv run python examples/parser.py
uv run python examples/sdp.py
uv run python examples/audio.py
uv run python examples/ivr_menu.py
uv run python examples/response_builders.py
uv run python examples/dialog_tracking.py
uv run python examples/routing.py
```

## Client (requires Asterisk)

| Example | Features | Description |
| --- | --- | --- |
| `quickstart.py` | register, options, send, call | One-liner functions |
| `call.py` | Client, create_sdp, dialog tracking | Complete call: REGISTER -> INVITE -> ACK -> BYE |
| `async_client.py` | AsyncClient, create_sdp | Full async client flow |
| `events.py` | Events, @on, EventContext | All event handler patterns |
| `dtmf.py` | RFC 4733, SIP INFO, inband | 3 DTMF sending methods |
| `dns_resolver.py` | SipResolver, AsyncSipResolver | DNS SRV resolution with fallback |
| `session_timers.py` | SessionTimer, Subscription | Session timers and event subscriptions |

```bash
cd docker/asterisk && docker-compose up -d
uv run python examples/quickstart.py
uv run python examples/call.py
uv run python examples/async_client.py
uv run python examples/events.py
uv run python examples/dtmf.py
uv run python examples/dns_resolver.py
uv run python examples/session_timers.py
```

## Server (self-contained, no Asterisk)

| Example | Features | Description |
| --- | --- | --- |
| `server.py` | SIPServer, @server.invite, DI, Annotated | Sync server with decorators + extractors |
| `async_server.py` | AsyncSIPServer, AsyncClient | Async server + client loopback |
| `ivr.py` | AsyncIVR, AsyncRTPSession, DTMF | Full IVR with real RTP + DTMF collection |

```bash
uv run python examples/server.py     # then test from another terminal
uv run python examples/async_server.py
uv run python examples/ivr.py
```

## Media

| Example | Features | Description |
| --- | --- | --- |
| `tts_stt.py` | BaseTTS, BaseSTT, FileTTS | TTS/STT adapter patterns |

## Contrib (SIP-I, ISUP)

| Example | Features | Description |
| --- | --- | --- |
| `sipi.py` | SipI, ISUP, PAI, cause mapping | International SIP-I gateway |
| `sipi_br.py` | SipIBR, ATI, ANATEL, Q.850 | Brazilian SIP-I (ANATEL/ISUP-BR) |

## Integration

| Example | Features | Description |
| --- | --- | --- |
| `fastapi_sip.py` | FastAPI, Client, REST+SIP | HTTP API wrapping SIP operations |

## Test Suite

| Example | Features | Description |
| --- | --- | --- |
| `asterisk.py` | All components, 3 auth policies | Comprehensive Asterisk integration test |

```bash
cd docker/asterisk && docker-compose up -d
uv run python examples/asterisk.py
```

See [docs/SDD.md](../docs/SDD.md) for the full spec.
