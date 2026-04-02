#!/usr/bin/env python3
"""
sipx — FastAPI + SIP integration example.

Runs a REST API alongside a SIP server. HTTP endpoints control SIP operations.

Requires: pip install fastapi uvicorn

Usage:
    uv run uvicorn examples.fastapi_sip:app --reload
    # or: uv run python examples/fastapi_sip.py

Test:
    curl http://localhost:8000/health
    curl -X POST http://localhost:8000/register -d '{"aor":"sip:1111@127.0.0.1","username":"1111","password":"1111xxx"}'
    curl -X POST http://localhost:8000/call -d '{"uri":"sip:100@127.0.0.1","username":"1111","password":"1111xxx"}'
"""

from rich.console import Console

from sipx import SIPClient

console = Console()

try:
    from fastapi import FastAPI
    from pydantic import BaseModel
except ImportError:
    console.print(
        "[red]This example requires: pip install fastapi uvicorn pydantic[/red]"
    )
    raise SystemExit(1)

# ---------------------------------------------------------------------------
# Pydantic models for API
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    aor: str
    username: str
    password: str


class CallRequest(BaseModel):
    uri: str
    username: str
    password: str
    duration: int = 5


class MessageRequest(BaseModel):
    uri: str
    content: str
    username: str = ""
    password: str = ""


class SipResponse(BaseModel):
    status_code: int
    reason: str


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="sipx API", version="0.3.0")


@app.get("/health")
def health():
    return {"status": "ok", "library": "sipx"}


@app.post("/register", response_model=SipResponse)
def register(req: RegisterRequest):
    """Register with a SIP server."""
    with SIPClient(local_port=0) as client:
        client.auth = (req.username, req.password)
        r = client.register(req.aor)
        return SipResponse(status_code=r.status_code, reason=r.reason_phrase)


@app.post("/options", response_model=SipResponse)
def options(uri: str):
    """Send OPTIONS to a SIP server."""
    with SIPClient(local_port=0) as client:
        r = client.options(uri)
        return SipResponse(status_code=r.status_code, reason=r.reason_phrase)


@app.post("/call", response_model=SipResponse)
def call(req: CallRequest):
    """Make a SIP call."""
    import time

    with SIPClient(local_port=0) as client:
        client.auth = (req.username, req.password)
        sdp = client.create_sdp()
        r = client.invite(to_uri=req.uri, body=sdp.to_string())

        if r.status_code == 200:
            client.ack()
            time.sleep(req.duration)
            client.bye()

        return SipResponse(status_code=r.status_code, reason=r.reason_phrase)


@app.post("/message", response_model=SipResponse)
def message(req: MessageRequest):
    """Send a SIP MESSAGE."""
    with SIPClient(local_port=0) as client:
        if req.username:
            client.auth = (req.username, req.password)
        r = client.message(to_uri=req.uri, content=req.content)
        return SipResponse(status_code=r.status_code, reason=r.reason_phrase)


if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Run with: uv run uvicorn examples.fastapi_sip:app[/red]")
        raise SystemExit(1)

    console.print("[bold]sipx — FastAPI + SIP[/bold]")
    console.print("http://localhost:8000/docs\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
