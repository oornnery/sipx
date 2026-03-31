# sipx -- TODO

## Recently Completed

- [x] `request.ok()` / `error()` / `trying()` / `ringing()` / `redirect()` response builders
- [x] `DialogTracker` -- auto dialog state for implicit `ack()` / `bye()`
- [x] `client.create_sdp(port)` helper
- [x] Auto `100 Trying` on INVITE in both SIPServer and AsyncSIPServer
- [x] RouteSet integration into Client ack/bye
- [x] Auto DNS SRV resolution in Client and AsyncClient (`auto_dns=True`)
- [x] Updated all 17 examples to use new patterns
- [x] Updated SDD (all sections)
- [x] `AsyncTimerManager` -- `asyncio.create_task(asyncio.sleep(delay))`
- [x] `AsyncSessionTimer` -- async refresh loop
- [x] `AsyncSubscription` -- async subscribe/refresh loop
- [x] `AsyncSIPServer` (native) -- `asyncio.DatagramProtocol`
- [x] `AsyncRTPSession` (native) -- `asyncio.DatagramProtocol`
- [x] `AsyncClient` (native) -- uses `AsyncUDPTransport` directly, no `to_thread`
- [x] `AsyncIVR` -- native async IVR controller
- [x] `AsyncATI` -- native async ATI portability query
- [x] `AsyncSipResolver` -- native async DNS resolver
- [x] SDP: ICE candidates, SRTP crypto, DTLS fingerprint, rtcp-fb, direction attributes
- [x] Real ISUP binary encoding (ITU-T Q.763): IAM, ACM, ANM, REL, RLC
- [x] SIP-I BR: ANATEL headers, ATI, ISUP-BR, number normalization
- [x] DTMF: RFC 4733 + SIP INFO + Inband (all 3 methods)
- [x] RTP: sync + async, tone generation, DTMF tone generation
- [x] IVR: Menu/Prompt/MenuItem models, sync + async controllers
- [x] TTS/STT: BaseTTS, BaseSTT adapters, Google TTS, Whisper STT
- [x] Removed all `print` from core (replaced with `logging`)
- [x] Removed all backward-compat aliases
- [x] Package-per-module architecture (client/, server/, fsm/, etc.)

## Async Gap -- Remaining

| Module | Status | Notes |
| --- | --- | --- |
| `media/_pyaudio.py` | Not async | Optional, low priority (softphone mode) |
| `transports/_ws.py` | Basic async | Review lock usage |

## Features Remaining

### High Priority

- [ ] SRTP packet encryption (RFC 3711) -- AES-128-CM, HMAC-SHA1
- [ ] RTCP (RFC 3550 Section 6) -- sender/receiver reports
- [ ] CI/CD (GitHub Actions) -- lint, test, coverage

### Medium Priority

- [ ] Jitter buffer for RTP receive
- [ ] Server-side FSMs (IST, NIST)
- [ ] WebSocket transport (full RFC 7118 compliance)
- [ ] IPv6 support (AAAA records in DNS resolver)
- [ ] NAPTR DNS records
- [ ] Coverage >80%

### Low Priority

- [ ] SCTP transport
- [ ] Conferencing (mixer)
- [ ] PyPI publishing
- [ ] Full SIP-I call flow automation

## Test Coverage (~60%)

607 tests passing. Areas needing more coverage:

- [ ] `client/` (33%) -- needs MockTransport integration tests
- [ ] `server/` (58%) -- needs loopback tests
- [ ] `media/_rtp.py` (57%) -- needs UDP loopback
- [ ] `contrib/_isup.py` (0%) -- needs encode/decode tests
- [ ] `contrib/_sipi_br.py` -- needs ATI/AsyncATI tests
