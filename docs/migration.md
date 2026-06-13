# Migration Guide: Old API to AsyncClient

This guide helps you move from the `SipUac` / `SipUas` API to the new `AsyncClient` API. The new design follows an httpx-like pattern: one client handles both UAC and UAS roles, configuration is centralized, and methods accept URI strings directly.

## Overview of API Changes

| Old API | New API |
| --- | --- |
| `SipUac` / `SipUas` | `AsyncClient` |
| `SipUserAgent` base class | Removed; use `AsyncClient` directly |
| `SipCall` object | `Response` object |
| `SipProvisionalResponse` | Removed; handle provisional logic in your UAS handler |
| `aor`, `registrar`, `remote` in constructor | Passed as URI strings to methods |
| `username`, `password` in constructor | `AuthFlow` object passed to constructor |
| `local_host`, `local_port`, `timeout` in constructor | `ClientConfig` dataclass |
| `mode="strict"` / `mode="lab"` | Removed; lab hooks not supported |
| UDP-only transport | UDP, TCP, and TLS supported |
| `event_hooks` dict | Same pattern, but `sdp` and `retransmission` hooks removed |
| `answer()` with built-in media | `on_invite` decorator + manual `Response` construction |
| `register()` returns `RegisterClientState` | `register()` returns `Response` |
| `call()` with built-in SDP/RTP | `invite()` with manual body; no built-in media |


## Side-by-Side Examples

### Client Initialization

**Old API:**

```python
from sipx import SipUac

uac = SipUac(
    aor="sip:alice@example.com",
    registrar="sip:example.com",
    remote=("example.com", 5060),
    username="alice",
    password="secret",
    local_host="0.0.0.0",
    local_port=5060,
    timeout=30.0,
)
```

**New API:**

```python
from sipx import AsyncClient, ClientConfig
from sipx.protocol.auth import AuthFlow

config = ClientConfig(
    local_host="0.0.0.0",
    local_port=5060,
    timeout=30.0,
)
auth = AuthFlow(username="alice", password="secret")
client = AsyncClient(transport="udp", config=config, auth=auth)
```


### Simple REGISTER

**Old API:**

```python
async with SipUac(
    aor="sip:alice@example.com",
    registrar="sip:example.com",
    username="alice",
    password="secret",
) as uac:
    state = await uac.register()
    print(state.value)
```

**New API:**

```python
async with AsyncClient(auth=AuthFlow(username="alice", password="secret")) as client:
    response = await client.register("sip:example.com")
    print(response.status_code)
```


### INVITE with SDP

**Old API:**

```python
async with SipUac(
    aor="sip:alice@example.com",
    registrar="sip:example.com",
    username="alice",
    password="secret",
) as uac:
    call = await uac.call("sip:bob@example.com", with_media=True)
    print(call.state)
    await uac.hangup(call)
```

**New API:**

```python
from sipx.sdp import create_audio_offer

async with AsyncClient(auth=AuthFlow(username="alice", password="secret")) as client:
    offer = create_audio_offer(
        connection_address="192.168.1.10",
        port=10000,
        codecs=("PCMU", "PCMA"),
    )
    response = await client.invite(
        "sip:bob@example.com",
        body=offer.to_sdp().encode("utf-8"),
        Content_Type="application/sdp",
    )
    print(response.status_code)
```


### Sending MESSAGE

**Old API:**

```python
async with SipUac(
    aor="sip:alice@example.com",
    registrar="sip:example.com",
) as uac:
    # MESSAGE sending was not a first-class method on SipUac
    pass
```

**New API:**

```python
async with AsyncClient() as client:
    response = await client.message("sip:bob@example.com", "Hello, Bob!")
    print(response.status_code)
```


### UAS Handlers

**Old API:**

```python
from sipx import SipUas, SipProvisionalResponse

uas = SipUas(aor="sip:bob@example.com")

async with uas:
    call = await uas.answer(
        provisionals=(
            SipProvisionalResponse.trying(),
            SipProvisionalResponse.ringing(),
        )
    )
    await uas.wait_hangup(call)
```

**New API:**

```python
from sipx import AsyncClient, Request, Response

client = AsyncClient()


@client.on_invite
async def handle_invite(request: Request) -> Response:
    return Response(
        status_code=200,
        reason="OK",
        headers={"Contact": "<sip:bob@example.com>"},
        body=None,
    )


async with client:
    # handle_request dispatches to the registered handler
    request = Request(
        method="INVITE",
        uri="sip:bob@example.com",
        headers={"Call-ID": "test-123"},
    )
    response = await client.handle_request(request)
    print(response.status_code)
```


### Event Hooks

**Old API:**

```python
def log_request(request, remote):
    print(f"Request: {request.method}")


def log_response(response, remote):
    print(f"Response: {response.status_code}")


uac = SipUac(
    aor="sip:alice@example.com",
    event_hooks={
        "request": [log_request],
        "response": [log_response],
        "wire": [debug_wire],
    },
)
```

**New API:**

```python
def log_request(request):
    print(f"Request: {request.method}")


def log_response(response):
    print(f"Response: {response.status_code}")


client = AsyncClient(
    event_hooks={
        "request": [log_request],
        "response": [log_response],
    },
)
```


## Common Patterns Migration

### Registration with Expires

**Old API:**

```python
uac = SipUac(
    aor="sip:alice@example.com",
    registrar="sip:example.com",
    expires=3600,
)
async with uac:
    state = await uac.register()
```

**New API:**

```python
client = AsyncClient()
async with client:
    response = await client.register(
        "sip:example.com",
        Expires="3600",
        From="<sip:alice@example.com>",
    )
```


### Unregister

**Old API:**

```python
state = await uac.unregister()
```

**New API:**

```python
response = await client.register(
    "sip:example.com",
    Expires="0",
    From="<sip:alice@example.com>",
)
```


### OPTIONS Ping

**Old API:**

```python
response = await uac.request(
    "OPTIONS",
    target="sip:example.com",
    remote=("example.com", 5060),
    caller="sip:alice@example.com",
    contact="sip:alice@example.com",
)
```

**New API:**

```python
response = await client.options("sip:example.com")
```


### SUBSCRIBE for Presence

**Old API:**

```python
# SUBSCRIBE was not a first-class method on SipUac
response = await uac.request(
    "SUBSCRIBE",
    target="sip:bob@example.com",
    remote=("example.com", 5060),
    caller="sip:alice@example.com",
    contact="sip:alice@example.com",
    headers=(("Event", "presence"), ("Expires", "3600")),
)
```

**New API:**

```python
response = await client.subscribe(
    "sip:bob@example.com",
    event="presence",
    Expires="3600",
)
```


## Breaking Changes

1. **SipUac and SipUas removed.** Use `AsyncClient` for both client and server roles.

2. **SipCall removed.** The new API returns `Response` objects. Call state, dialogs, and media must be managed manually.

3. **Constructor parameters moved.** `aor`, `registrar`, `remote`, `username`, `password`, and `contact_user` are no longer accepted by the client constructor. Pass URIs to methods and credentials via `AuthFlow`.

4. **SipProvisionalResponse removed.** UAS provisional responses are no longer configured with `SipProvisionalResponse`. Build `Response` objects with status codes in the `1xx` range inside your handler.

5. **Built-in RTP/media removed.** `AsyncClient` does not open RTP sinks or sessions. Use `RtpAudioSession`, `RtpSink`, and SDP helpers from `sipx.rtp` and `sipx.sdp` directly.

6. **`call()` renamed to `invite()`.** The method no longer handles SDP offer creation or RTP session setup automatically.

7. **`register()` returns `Response`, not `RegisterClientState`.** Check `response.status_code` to determine success.

8. **`answer()`, `hangup()`, `wait_hangup()` removed from UAS.** Use `on_invite` / `on_message` decorators plus `handle_request()` to process incoming requests. Out-of-dialog requests like BYE are not yet handled automatically.

9. **`mode="lab"` removed.** The lab mode for malformed messages and protocol overrides is not supported. Use the low-level `sipx.sip` message builders for custom messages.

10. **`sdp`, `retransmission`, and `wire` event hooks removed.** Only `request`, `response`, and `provisional` hooks are supported.

11. **`compact_headers` parameter removed.** Header serialization always uses canonical names.

12. **`timeline` and `actor_id` parameters removed.** The new client does not record timeline events internally. Use `event_hooks` to log externally.

13. **Transport selection changed.** Pass `transport="udp"`, `transport="tcp"`, or `transport="tls"` to the constructor instead of relying on UDP-only `SipUdpEndpoint`.

14. **`timeout` behavior changed.** Timeouts are now handled via `asyncio.wait_for` internally and raise `SipTimeoutError` instead of `SipUdpError`.


## FAQ

### How do I migrate code that relied on SipCall state?

Store the `Response` object and track state in your application. For dialog management, inspect the `Call-ID`, `From`, and `To` headers manually or use `Dialog` from `sipx.protocol.dialog`.

### Where did the automatic SDP offer/answer go?

You must build SDP bodies with `sipx.sdp.create_audio_offer` and `sipx.sdp.create_audio_answer`, then pass them as `body` and `Content-Type` headers to `invite()` or return them in your UAS `Response`.

### Can I still send DTMF?

`AsyncClient` does not have a `send_dtmf()` method. Send an in-dialog INFO with the generic escape hatch: `await client.request("INFO", uri, body=b"Signal=1\r\nDuration=160\r\n", **{"Content-Type": "application/dtmf-relay"})`.

### How do I handle authentication?

Create an `AuthFlow` object and pass it to `AsyncClient`. The client automatically retries on `401` and `407` responses.

```python
from sipx.protocol.auth import AuthFlow

auth = AuthFlow(username="alice", password="secret")
client = AsyncClient(auth=auth)
```

### What happened to event_hooks["wire"]? 

The `wire` hook is no longer supported. Use `request` and `response` hooks to inspect traffic, or access the transport directly via `client.transport`.

### How do I run a UAS that waits for incoming calls?

The new API is request/response oriented. Register handlers with `on_invite`, then feed incoming `Request` objects to `handle_request()`. There is no blocking `answer()` method.

```python
@client.on_invite
async def handle_invite(request: Request) -> Response:
    return Response(200, "OK", {}, None)


response = await client.handle_request(incoming_request)
```

### Is there a context manager?

Yes. Both old and new APIs support `async with`. The new client starts the transport and receive loop on enter, and closes them on exit.

```python
async with AsyncClient() as client:
    response = await client.register("sip:example.com")
```

### Can I use TCP or TLS?

Yes. Pass `transport="tcp"` or `transport="tls"` to the constructor.

```python
client = AsyncClient(transport="tls")
```

### Is there a FastAPI example?

Yes. The workspace app `apps/fastapi` (`sipx-fastapi`) wraps `AsyncClient` in a
FastAPI lifespan and exposes REST endpoints for OPTIONS, REGISTER, MESSAGE, and
generic SIP requests. See `apps/fastapi/README.md`.

```bash
uv run --package sipx-fastapi sipx-fastapi
curl -s http://127.0.0.1:8000/health
```

### How do I set custom headers on every request?

Use `ClientConfig.headers` for default headers, or pass them as keyword arguments to individual methods.

```python
config = ClientConfig(headers={"X-Custom": "value"})
client = AsyncClient(config=config)

# Or per-request
response = await client.options("sip:example.com", X_Custom="override")
```
