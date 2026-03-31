# sipx — TODO

## Done (this session)

- [x] Native AsyncClient — rewritten as thin wrapper over sync Client (-532 lines)
- [x] AsyncSIPServer — async wrapper with decorators + DI
- [x] AsyncRTPSession, AsyncCallSession, AsyncDTMFHelper — full async media
- [x] Server decorators — @server.invite, @server.handle("METHOD")
- [x] DI extractors — Annotated[str, FromHeader], AutoRTP, Header("X"), etc.
- [x] SDPBody.audio() — 1-line SDP factory
- [x] Tuple auth — client.auth = ("user", "pass")
- [x] Auto-retry 401/407 — auto_auth=True
- [x] Audio generators — ToneGenerator, SilenceGenerator, NoiseGenerator, DTMFToneGenerator
- [x] CallSession — wraps RTP + DTMF in one object
- [x] One-liners — sipx.register(), sipx.options(), sipx.call(), sipx.send()
- [x] sipx.media / sipx.contrib — public packages (no underscores)
- [x] Security hardening — TLS verify warning, MD5 fallback warning
- [x] 10 examples — quickstart, call_flow, events, dtmf, sdp, audio, parser, server, ivr, asterisk_full

## Test Coverage (current: 55%, target: 80%+)

### Well covered (>80%)

- `_events.py` — 98%
- `_models/_header.py` — 99%
- `_models/_auth.py` — 92%
- `_depends.py` — 92%
- `_models/_message.py` — 88%
- `_transports/_base.py` — 83%
- `_models/_body.py` — 82%
- `_types.py` — 80%
- `_media/_codecs.py` — 100%
- `_media/_generators.py` — 100%

### Needs tests

- [ ] `_client.py` (24%) — request(), SIP methods, auto-retry with MockTransport
- [ ] `_server.py` (56%) — _run() loop, DI handler invocation
- [ ] `_fsm.py` (72%) — IST/NIST full transitions, timer firing
- [ ] `_media/_rtp.py` (57%) — RTPSession start/stop, send_audio, recv_audio
- [ ] `_media/_session.py` (53%) — CallSession play, record, hangup
- [ ] `_media/_dtmf.py` (31%) — DTMFSender.send_digit, DTMFCollector.collect
- [ ] `_media/_audio.py` (29%) — AudioPlayer, AudioRecorder with WAV files
- [ ] `_media/_async.py` (0%) — AsyncRTPSession, AsyncCallSession
- [ ] `_transports/` (0-20%) — UDP/TCP/TLS loopback or socket mocks
- [ ] `_contrib/_fastapi.py` (0%) — SIPRouter with FastAPI TestClient
- [ ] `main.py` (0%) — CLI with typer CliRunner

## Features to Implement

### High Priority

- [ ] Complete SIP URI parser (RFC 3986) — current is partial
- [ ] SRTP (RFC 3711) — AES-128-CM, HMAC-SHA1, key exchange via SDP
- [ ] DNS SRV resolution (RFC 3263) — auto-resolve SIP server from domain

### Medium Priority

- [ ] SIP-I BR (ANATEL) — Brazilian ISUP-BR cause codes, portability headers
- [ ] WebSocket transport (RFC 7118) — stub exists, needs websockets integration
- [ ] Session Timers (RFC 4028) — auto-refresh sessions
- [ ] Route/Record-Route processing — proper SIP routing
- [ ] SUBSCRIBE/NOTIFY complete — subscription state, auto-renewal, PIDF parsing
- [ ] Opus codec — wideband audio

### Low Priority

- [ ] IPv6 support
- [ ] PyAudio integration — mic/speaker I/O for softphone mode
- [ ] SCTP transport
- [ ] Conferencing (audio mixer)
