# sipx — TODO

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
- [ ] `_transports/` (0-20%) — UDP/TCP/TLS loopback or socket mocks
- [ ] `_contrib/_fastapi.py` (0%) — SIPRouter with FastAPI TestClient
- [ ] `main.py` (0%) — CLI with typer CliRunner

## Features to Implement

### High Priority

- [ ] Native AsyncClient — current has bugs in request(), needs full rewrite
- [ ] SRTP (RFC 3711) — `_srtp/` stub exists, needs AES-128-CM implementation
- [ ] DNS SRV resolution (RFC 3263) — replace static IP:port with dynamic lookup
- [ ] Complete SIP URI parser (RFC 3986) — current is partial

### Medium Priority

- [ ] SIP-I BR (ANATEL) — Brazilian ISUP-BR cause codes, portability headers
- [ ] WebSocket transport (RFC 7118) — stub exists, needs `websockets` integration
- [ ] Session Timers (RFC 4028) — auto-refresh sessions
- [ ] Route/Record-Route processing — proper SIP routing
- [ ] SUBSCRIBE/NOTIFY complete — subscription state, auto-renewal, PIDF parsing
- [ ] Opus codec — wideband audio

### Low Priority

- [ ] IPv6 support
- [ ] PyAudio integration — mic/speaker I/O for softphone mode
- [ ] SCTP transport
- [ ] Conferencing (audio mixer)
