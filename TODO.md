# sipx -- TODO

## Done

### Core SIP

- [x] Client sync + AsyncClient native (asyncio, no to_thread wrapper)
- [x] SIPServer sync + AsyncSIPServer (asyncio.DatagramProtocol)
- [x] 14 SIP methods (INVITE, REGISTER, BYE, ACK, CANCEL, OPTIONS, MESSAGE, SUBSCRIBE, NOTIFY, REFER, INFO, UPDATE, PRACK, PUBLISH)
- [x] Digest authentication (MD5, SHA-256, auto-retry on 401/407)
- [x] Transaction FSM (ICT, NICT, IST, NIST) with Timer A/B/D/E/F/G/H/I/J/K
- [x] Timer retransmission wired into Client.request() (Timer A for INVITE, Timer E for non-INVITE)
- [x] Dialog state tracking (DialogTracker — implicit ack/bye without passing response)
- [x] Response builders (request.ok/trying/ringing/error/redirect)
- [x] Auto 100 Trying on INVITE in server (RFC 3261 Section 8.2.6.1)
- [x] Route/Record-Route processing (RouteSet applied in ack/bye)
- [x] DNS SRV resolution (RFC 3263) — SipResolver + AsyncSipResolver, auto in Client
- [x] SIP URI parser (RFC 3986) — SipURI.parse, used in _extract_host_port
- [x] Session Timers (RFC 4028) — SessionTimer + AsyncSessionTimer
- [x] Subscription model (RFC 6665) — Subscription + AsyncSubscription
- [x] Auto re-registration with callback
- [x] Context manager (with/async with) for Client and Server
- [x] Timeout returns None (no exception)

### API

- [x] FastAPI-style server decorators (@server.invite, @server.register, @server.handle)
- [x] Annotated DI extractors (FromHeader, ToHeader, CallID, Header, Source, AutoRTP, custom Extractor)
- [x] Events system (@on decorator, method/status filters, multi-method, global hooks)
- [x] client.create_sdp(port) helper
- [x] Top-level one-liners (sipx.options, sipx.register, sipx.send, sipx.call)

### Transport

- [x] UDP sync + async (UDPTransport, AsyncUDPTransport — DatagramProtocol)
- [x] TCP sync + async (TCPTransport, AsyncTCPTransport)
- [x] TLS sync + async (TLSTransport, AsyncTLSTransport)
- [x] WebSocket transport (RFC 7118 — basic)

### SDP

- [x] SDPBody with offer/answer model (RFC 4566, RFC 3264)
- [x] ICE candidates, SRTP crypto attributes, DTLS fingerprint
- [x] rtcp-fb attributes, direction (sendrecv/sendonly/recvonly/inactive)
- [x] RawBody for non-SDP content types

### Media

- [x] RTP engine sync + async (RTPPacket, RTPSession, AsyncRTPSession — DatagramProtocol)
- [x] DTMF 3 methods: RFC 4733 (RTP telephone-event), SIP INFO, Inband audio
- [x] DTMFSender, DTMFCollector, AsyncDTMFHelper
- [x] CallSession + AsyncCallSession
- [x] ToneGenerator, SilenceGenerator, NoiseGenerator
- [x] DTMFToneGenerator (dual-tone 697+1477Hz etc.)
- [x] G.711 codecs (PCMU/PCMA encode/decode)
- [x] Opus codec adapter (requires opuslib)
- [x] TTS/STT adapter interfaces (BaseTTS, BaseSTT)
- [x] Google TTS adapter, Whisper STT adapter
- [x] AudioPlayer, AudioRecorder
- [x] PyAudio adapter (mic/speaker I/O — planned for softphone)

### SIP-I / Brazil

- [x] Real ISUP binary encoding (ITU-T Q.763): IAM, ACM, ANM, REL, RLC
- [x] BCD phone number encoding/decoding
- [x] SIP-I international with multipart/mixed body
- [x] SIP-I BR: ANATEL, ATI + AsyncATI portability query
- [x] ISUP-BR headers: P-Charging-Vector, P-Access-Network-Info, P-Charging-Function-Addresses
- [x] Reason header (Q.850 cause codes)
- [x] Brazilian number normalization and validation

### Contrib

- [x] IVR builder: Menu, MenuItem, Prompt models
- [x] IVR sync + AsyncIVR (native async)
- [x] FastAPI integration adapter

### Logging

- [x] Comprehensive logging across 26+ modules (child loggers per subsystem)
- [x] FSM: transaction/dialog create, state transitions, timer start/cancel/expire
- [x] Transports: bind, connect, send/recv bytes, errors, close
- [x] DNS: SRV resolve, fallback, failures
- [x] Media: RTP session lifecycle, send/recv packets, DTMF send/collect
- [x] Session: timer start/refresh/stop, subscription lifecycle
- [x] Contrib: ISUP encode/decode, SIP-I, IVR session, ATI queries
- [x] Models: parse errors, auth challenges
- [x] Core: routing, URI parse, DI resolution
- [x] No print in core — all logging via `logging.getLogger("sipx")`

### CI/CD

- [x] GitHub Actions CI (lint + test on push to dev, PR to dev/master)
- [x] Asterisk integration workflow (Docker, wait for ready, smoke tests)
- [x] Create Release workflow (auto-create GitHub release on push to master)
- [x] Publish Package workflow (PyPI publish on release via trusted publisher)
- [x] Version management (_version.py single source of truth)

### Testing

- [x] 607 unit tests, ~60% coverage
- [x] Integration test suite (tests/integration/test_asterisk.py)
- [x] Asterisk Docker environment (3 auth policies, anonymous OPTIONS)

### Documentation

- [x] SDD (docs/SDD.md) — full spec, mermaid diagrams, roadmap
- [x] README.md — quick start, features, RFC table, examples
- [x] examples/README.md — 22 examples categorized
- [x] 22 examples covering all major features

### Examples

- [x] quickstart.py, call.py, async_client.py, events.py, dtmf.py
- [x] server.py, async_server.py, ivr.py, ivr_menu.py
- [x] sdp.py, audio.py, parser.py, tts_stt.py
- [x] sipi.py, sipi_br.py, fastapi_sip.py, asterisk.py
- [x] response_builders.py, dialog_tracking.py, routing.py
- [x] dns_resolver.py, session_timers.py

---

## In Progress

### Bug Fixes

- [ ] Verify retransmission logs appear in sngrep when no peer responds (Timer E/A wired but needs live testing)

---

## Features Remaining

### High Priority

- [ ] SRTP packet encryption (RFC 3711) — AES-128-CM, HMAC-SHA1-80
- [ ] RTCP sender/receiver reports (RFC 3550 Section 6)
- [ ] Coverage >80% — current ~60%, need more client/server/media tests

### Medium Priority

- [ ] Jitter buffer for RTP receive path
- [ ] Complete PRACK / 100rel flow (RFC 3262)
- [ ] SIP over WebSocket full compliance (RFC 7118 — keepalive, framing)
- [ ] IPv6 support (AAAA records in DNS resolver, IPv6 transports)
- [ ] NAPTR DNS records (RFC 3263 full)
- [ ] Forking (handle multiple 200 OK from different UAS)
- [ ] Server-side FSM integration (IST/NIST wired into server handlers)
- [ ] PyPI publishing (package ready, needs trusted publisher config)

### Low Priority

- [ ] SCTP transport
- [ ] Conferencing (audio mixer)
- [ ] ICE connectivity checks (STUN/TURN)
- [ ] SRTP-DTLS key exchange
- [ ] Call transfer (REFER flow end-to-end)
- [ ] Presence agent (PUBLISH/SUBSCRIBE/NOTIFY full flow)
- [ ] B2BUA (back-to-back user agent)
- [ ] TUI dashboard (textual — call monitor)
- [ ] CLI tools (typer — SIP testing CLI)

### Test Coverage Gaps

- [ ] `client/` (33%) — MockTransport integration tests
- [ ] `server/` (58%) — loopback tests with DI
- [ ] `media/_rtp.py` (57%) — UDP loopback, packet loss simulation
- [ ] `contrib/_isup.py` (0%) — encode/decode roundtrip tests
- [ ] `contrib/_sipi_br.py` — ATI/AsyncATI tests
- [ ] `fsm/` — timer firing, state transition edge cases
- [ ] `transports/` — TCP/TLS connection lifecycle tests
