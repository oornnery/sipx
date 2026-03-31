# sipx — TODO

## Async Gap — modules using threading that need native async versions

### Has async wrapper (to_thread) but internal threading.Timer/Thread

| Module | Threading usage | Async wrapper | Needs native async |
|--------|----------------|---------------|-------------------|
| `_fsm.py` (TimerManager) | `threading.Timer` for retransmission | None | `AsyncTimerManager` with `asyncio.create_task(asyncio.sleep())` |
| `_session_timer.py` | `threading.Timer` for refresh | None | `AsyncSessionTimer` with `asyncio.sleep` loop |
| `_subscription.py` | `threading.Timer` for auto-refresh | None | `AsyncSubscription` with `asyncio.sleep` loop |
| `_client.py` (auto-reregister) | `threading.Timer` for re-registration | `AsyncClient` uses `asyncio.sleep` (done) | Done |
| `_server.py` (SIPServer) | `threading.Thread` for main loop | `AsyncSIPServer` (to_thread) | Native `asyncio.start_server` |
| `media/_rtp.py` (RTPSession) | `threading.Thread` for recv loop | `AsyncRTPSession` (to_thread) | Native `asyncio.DatagramProtocol` |
| `media/_pyaudio.py` | `threading.Thread` for capture/playback | None | `AsyncMicrophoneSource`/`AsyncSpeakerSink` |
| `transports/_ws.py` (WSTransport) | `threading.Lock` | `AsyncWSTransport` exists | Review lock usage |

### Already native async (no changes needed)

| Module | Status |
|--------|--------|
| `AsyncClient` | Uses `asyncio.to_thread` for sync Client + `asyncio.sleep` for reregister |
| `AsyncSIPServer` | Wraps sync via `to_thread` |
| `AsyncRTPSession` | Wraps sync via `to_thread` |
| `AsyncCallSession` | Wraps sync via `to_thread` |
| `AsyncDTMFHelper` | Wraps sync via `to_thread` |
| `AsyncUDPTransport` | Native `asyncio.DatagramProtocol` |
| `AsyncTCPTransport` | Native `asyncio.open_connection` |
| `AsyncTLSTransport` | Native `asyncio.open_connection` + SSL |
| `AsyncWSTransport` | Native `websockets.connect` |

### Priority for native async rewrite

1. [ ] `AsyncTimerManager` — `asyncio.create_task(asyncio.sleep(delay))` instead of `threading.Timer`
2. [ ] `AsyncSessionTimer` — uses AsyncTimerManager, `await client.update()`
3. [ ] `AsyncSubscription` — uses AsyncTimerManager, `await client.subscribe()`
4. [ ] `AsyncSIPServer` (native) — `asyncio.DatagramProtocol` instead of threading
5. [ ] `AsyncRTPSession` (native) — `asyncio.DatagramProtocol` for recv instead of thread
6. [ ] `AsyncMicrophoneSource` / `AsyncSpeakerSink` — optional, low priority

## Features Remaining

### High Priority

- [ ] SRTP (RFC 3711) — AES-128-CM, HMAC-SHA1

### Medium Priority

- [ ] WebSocket keepalive (RFC 7118 Section 3.2)
- [ ] SDP advanced attributes (ICE, crypto, rtcp-fb)
- [ ] IPv6 support (AAAA records in DNS resolver)
- [ ] NAPTR DNS records
- [ ] SCTP transport

### Test Coverage (60%)

- [ ] `_client.py` (33%) — needs MockTransport integration tests
- [ ] `_server.py` (58%) — needs loopback tests
- [ ] `media/_rtp.py` (57%) — needs UDP loopback
- [ ] `contrib/_isup.py` (0%) — needs encode/decode tests
