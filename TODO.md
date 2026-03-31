# sipx — TODO

## Done (this session)

- [x] Native AsyncClient — thin wrapper over sync Client (-532 lines)
- [x] AsyncSIPServer, AsyncRTPSession, AsyncCallSession, AsyncDTMFHelper
- [x] Server decorators + DI extractors (Annotated)
- [x] SDPBody.audio(), tuple auth, auto-retry, one-liners
- [x] Audio generators, CallSession, DTMFHelper
- [x] sipx.media / sipx.contrib public packages
- [x] Security hardening (TLS verify warning, MD5 fallback warning)
- [x] 10 examples
- [x] SIP URI parser (RFC 3261 Section 19.1) — SipURI dataclass
- [x] Session Timers (RFC 4028) — SessionTimer auto-refresh
- [x] Route/Record-Route processing (RFC 3261 Section 16) — RouteSet
- [x] SUBSCRIBE/NOTIFY complete (RFC 6665) — Subscription manager
- [x] Opus codec (RFC 6716) — optional opuslib
- [x] PyAudio integration — MicrophoneSource + SpeakerSink
- [x] Refactor: DTMFEvent, SipI, Extractor.resolve_handler
- [x] SIP-I BR (ANATEL) — ATI portability, Reason Q.850, P-Charging-Function-Addresses
- [x] DNS SRV resolution (RFC 3263) — SipResolver with SRV + A fallback
- [x] 607 tests (60% coverage)

## Test Coverage (current: 60%)

### 90%+ (done)

- `_uri.py` — 100%
- `_routing.py` — 100%
- `_media/_codecs.py` — 100%
- `_media/_generators.py` — 100%
- `_models/_header.py` — 99%
- `_events.py` — 98%
- `_subscription.py` — 97%
- `_session_timer.py` — 96%
- `_contrib/_sipi_br.py` — 96%
- `_contrib/_sipi.py` — 96%
- `_depends.py` — 92%
- `_models/_auth.py` — 92%
- `_dns.py` — 92%

### Needs improvement

- [ ] `_models/_message.py` (88%) — edge cases
- [ ] `_models/_body.py` (85%) — SDP parsing edge cases
- [ ] `_transports/_base.py` (83%) — ABC coverage
- [ ] `_types.py` (80%) — TransportAddress.from_uri
- [ ] `_fsm.py` (72%) — IST/NIST timer callbacks

### Needs mocks/network (hard to test)

- [ ] `_client.py` (33%) — needs full MockTransport flow
- [ ] `_server.py` (58%) — needs loopback integration
- [ ] `_media/_rtp.py` (57%) — needs UDP loopback
- [ ] `_media/_session.py` (53%) — needs mock RTP
- [ ] `_media/_dtmf.py` (44%) — needs RTP loopback
- [ ] `_transports/` (0-20%) — needs socket mocks

### Stubs (optional deps, 0%)

- `_media/_opus.py` — needs opuslib
- `_media/_pyaudio.py` — needs pyaudio
- `_media/_async.py` — needs async test framework
- `_transports/_ws.py` — needs websockets
- `_contrib/_fastapi.py` — needs fastapi
- `main.py` — needs typer CliRunner

## Features Remaining

### High Priority

- [ ] SRTP (RFC 3711) — AES-128-CM, HMAC-SHA1

### Medium Priority

- [ ] WebSocket transport (RFC 7118) — real websockets integration
- [ ] IPv6 support
- [ ] SCTP transport
- [ ] Conferencing (audio mixer)
