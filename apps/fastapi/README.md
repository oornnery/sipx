# sipx FastAPI

Minimal FastAPI service that exposes [sipx](https://github.com/oornnery/sipx) `AsyncClient` operations over HTTP. Use it as a reference for wiring `AsyncClient` into a web stack with a shared lifespan-managed client.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service and SIP config summary (no network I/O) |
| `POST` | `/sip/options` | OPTIONS capability probe |
| `POST` | `/sip/register` | REGISTER with configurable `expires` |
| `POST` | `/sip/unregister` | REGISTER with `Expires: 0` |
| `POST` | `/sip/message` | SIP MESSAGE |
| `POST` | `/sip/request` | Arbitrary SIP method (INFO, NOTIFY, etc.) |

Successful SIP calls return JSON with `status_code`, `reason`, `headers`, `body`, and `history` (provisional and Digest challenge responses collected by `AsyncClient`).

## Configuration

SIP settings reuse the same `SIPX_*` variables as the root examples and CLI:

```bash
export SIPX_AOR=sip:1001@example.com
export SIPX_REGISTRAR=sip:pbx.example.com:5060
export SIPX_USERNAME=1001
export SIPX_PASSWORD=...
export SIPX_LOCAL_HOST=0.0.0.0
export SIPX_LOCAL_PORT=0
export SIPX_TIMEOUT=10
export SIPX_TRANSPORT=udp
```

HTTP server bind settings:

```bash
export SIPX_FASTAPI_HOST=127.0.0.1
export SIPX_FASTAPI_PORT=8000
```

## Run

From the repository root:

```bash
uv sync --all-groups
uv run --package sipx-fastapi sipx-fastapi
```

Or with uvicorn directly:

```bash
uv run --package sipx-fastapi uvicorn sipx_fastapi.app:app --host 127.0.0.1 --port 8000
```

## Example requests

```bash
curl -s http://127.0.0.1:8000/health | jq .

curl -s -X POST http://127.0.0.1:8000/sip/options \
  -H 'Content-Type: application/json' \
  -d '{"target":"sip:pbx.example.com"}' | jq .

curl -s -X POST http://127.0.0.1:8000/sip/register \
  -H 'Content-Type: application/json' \
  -d '{"expires":3600}' | jq .

curl -s -X POST http://127.0.0.1:8000/sip/message \
  -H 'Content-Type: application/json' \
  -d '{"target":"sip:1002@example.com","text":"hello from fastapi"}' | jq .

curl -s -X POST http://127.0.0.1:8000/sip/request \
  -H 'Content-Type: application/json' \
  -d '{"method":"INFO","target":"sip:1002@example.com","body":"Signal=1\\r\\nDuration=160\\r\\n","content_type":"application/dtmf-relay"}' | jq .
```

## Tests

```bash
uv run pytest apps/fastapi/tests/test_app.py
```

## Related examples

- Root scripts: `sipx.examples.options`, `sipx.examples.message`, `sipx.examples.register`
- CLI: `uv run --package sipx-cli sipx options ...`
- Migration notes: `docs/migration.md`
