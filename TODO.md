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
- [x] Refactor: DTMFEvent, SipI, Extractor.resolve_handler (no standalone funcs)

## Test Coverage (current: 55%, target: 80%+)

### Needs tests

- [ ] `_client.py` (24%) — request(), SIP methods with MockTransport
- [ ] `_server.py` (56%) — _run() loop, DI handler invocation
- [ ] `_media/_rtp.py` (57%) — RTPSession start/stop, send/recv
- [ ] `_media/_session.py` (53%) — CallSession play, record, hangup
- [ ] `_media/_dtmf.py` (31%) — DTMFSender.send_digit, DTMFCollector.collect
- [ ] `_media/_async.py` (0%) — async wrappers
- [ ] `_session_timer.py` (0%) — SessionTimer refresh loop
- [ ] `_routing.py` (0%) — RouteSet from_response, apply
- [ ] `_subscription.py` (0%) — Subscription lifecycle
- [ ] `_transports/` (0-20%) — UDP/TCP/TLS
- [ ] `main.py` (0%) — CLI typer

## Features to Implement

### High Priority

- [ ] SRTP (RFC 3711) — AES-128-CM, HMAC-SHA1
- [x] DNS SRV resolution (RFC 3263) — SipResolver with SRV + A fallback

### Medium Priority

- [x] SIP-I BR (ANATEL) — ATI portability, Reason Q.850, P-Charging-Function-Addresses
- [ ] WebSocket transport (RFC 7118) — real websockets integration
- [ ] IPv6 support
- [ ] SCTP transport
- [ ] Conferencing (audio mixer)
