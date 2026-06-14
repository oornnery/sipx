"""FastAPI application exposing sipx AsyncClient over HTTP."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from sipx import AsyncClient, AuthDigest
from sipx.config import Settings as SipSettings
from sipx.exceptions import AuthError, ProtocolError, TimeoutError as SipTimeoutError

from sipx_fastapi.config import Settings, load_settings
from sipx_fastapi.serializers import response_payload


class OptionsRequest(BaseModel):
    target: str = Field(..., description="SIP URI to query with OPTIONS.")


class RegisterRequest(BaseModel):
    registrar: str | None = Field(
        default=None,
        description="Registrar URI; defaults to SIPX_REGISTRAR.",
    )
    expires: int = Field(default=3600, ge=0, description="Registration lifetime.")


class MessageRequest(BaseModel):
    target: str = Field(..., description="Destination SIP URI.")
    text: str = Field(default="", description="MESSAGE body text.")
    content_type: str = Field(
        default="text/plain",
        description="Content-Type header for the MESSAGE body.",
    )


class InviteRequest(BaseModel):
    target: str = Field(..., description="Target SIP URI to call.")
    call_id: str | None = Field(
        default=None,
        description="Optional Call-ID; supply it to cancel the call concurrently.",
    )
    body: str | None = Field(default=None, description="Optional SDP/offer body.")
    content_type: str | None = Field(
        default="application/sdp",
        description="Content-Type when body is set.",
    )
    headers: dict[str, str] = Field(default_factory=dict)


class CancelRequest(BaseModel):
    call_id: str = Field(..., description="Call-ID of the pending INVITE to cancel.")


class GenericSipRequest(BaseModel):
    method: str = Field(..., description="SIP method, for example INFO or NOTIFY.")
    target: str = Field(..., description="Request-URI.")
    headers: dict[str, str] = Field(default_factory=dict)
    body: str | None = Field(default=None, description="Optional request body.")
    content_type: str | None = Field(
        default=None,
        description="Content-Type when body is set.",
    )


def build_client(app_settings: Settings) -> AsyncClient:
    """Create an AsyncClient from service settings."""
    sip_settings = SipSettings(
        local_host=app_settings.local_host,
        local_port=app_settings.local_port,
        timeout=app_settings.timeout,
        from_uri=app_settings.aor,
        contact_uri=app_settings.aor,
        user_agent=app_settings.user_agent,
    )
    auth = None
    if app_settings.auth_configured:
        auth = AuthDigest(username=app_settings.username, password=app_settings.password)
    return AsyncClient(
        transport=app_settings.transport, settings=sip_settings, auth=auth
    )


def _get_client(request: Request) -> AsyncClient:
    client = getattr(request.app.state, "sip_client", None)
    if client is None:
        raise HTTPException(status_code=503, detail="SIP client is not initialized")
    return client


async def _run_sip(coro) -> dict[str, Any]:
    try:
        response = await coro
    except SipTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ProtocolError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return response_payload(response)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    client = build_client(settings)
    await client.__aenter__()
    app.state.settings = settings
    app.state.sip_client = client
    try:
        yield
    finally:
        await client.__aexit__(None, None, None)


def create_app(
    *, settings: Settings | None = None, client: AsyncClient | None = None
) -> FastAPI:
    """Build the FastAPI app, optionally injecting settings/client for tests."""
    if settings is None and client is None:
        app = FastAPI(
            title="sipx FastAPI",
            description="REST endpoints over sipx AsyncClient for OPTIONS, REGISTER, MESSAGE, INVITE, CANCEL, and raw SIP requests.",
            lifespan=lifespan,
        )
    else:
        app = FastAPI(
            title="sipx FastAPI",
            description="REST endpoints over sipx AsyncClient for OPTIONS, REGISTER, MESSAGE, INVITE, CANCEL, and raw SIP requests.",
        )
        app.state.settings = settings or load_settings()
        app.state.sip_client = client

    @app.get("/health")
    async def health(request: Request) -> dict[str, Any]:
        settings_obj: Settings = request.app.state.settings
        return {
            "status": "ok",
            "sip": {
                "aor": settings_obj.aor,
                "registrar": settings_obj.registrar,
                "transport": settings_obj.transport,
                "local_host": settings_obj.local_host,
                "local_port": settings_obj.local_port,
                "timeout": settings_obj.timeout,
                "auth_configured": settings_obj.auth_configured,
            },
        }

    @app.post("/sip/options")
    async def sip_options(body: OptionsRequest, request: Request) -> dict[str, Any]:
        client = _get_client(request)
        return await _run_sip(client.options(body.target))

    @app.post("/sip/register")
    async def sip_register(body: RegisterRequest, request: Request) -> dict[str, Any]:
        client = _get_client(request)
        settings_obj: Settings = request.app.state.settings
        registrar = body.registrar or settings_obj.registrar
        return await _run_sip(
            client.register(registrar, **{"Expires": str(body.expires)})
        )

    @app.post("/sip/unregister")
    async def sip_unregister(body: RegisterRequest, request: Request) -> dict[str, Any]:
        client = _get_client(request)
        settings_obj: Settings = request.app.state.settings
        registrar = body.registrar or settings_obj.registrar
        return await _run_sip(client.register(registrar, **{"Expires": "0"}))

    @app.post("/sip/message")
    async def sip_message(body: MessageRequest, request: Request) -> dict[str, Any]:
        client = _get_client(request)
        headers = {"Content-Type": body.content_type}
        return await _run_sip(client.message(body.target, body.text, **headers))

    @app.post("/sip/invite")
    async def sip_invite(body: InviteRequest, request: Request) -> dict[str, Any]:
        client = _get_client(request)
        kwargs: dict[str, Any] = dict(body.headers)
        if body.call_id:
            kwargs["Call-ID"] = body.call_id
        if body.body is not None:
            payload = body.body.encode("utf-8")
            kwargs["body"] = payload
            kwargs.setdefault("Content-Length", str(len(payload)))
            if body.content_type:
                kwargs["Content-Type"] = body.content_type
        return await _run_sip(client.invite(body.target, **kwargs))

    @app.post("/sip/cancel")
    async def sip_cancel(body: CancelRequest, request: Request) -> dict[str, Any]:
        client = _get_client(request)
        if body.call_id not in client._pending_invites:
            raise HTTPException(
                status_code=409,
                detail="no pending INVITE for that Call-ID",
            )
        return await _run_sip(client.cancel(body.call_id))

    @app.post("/sip/request")
    async def sip_request(body: GenericSipRequest, request: Request) -> dict[str, Any]:
        client = _get_client(request)
        kwargs: dict[str, Any] = dict(body.headers)
        if body.body is not None:
            payload = body.body.encode("utf-8")
            kwargs["body"] = payload
            kwargs.setdefault("Content-Length", str(len(payload)))
            if body.content_type:
                kwargs["Content-Type"] = body.content_type
        return await _run_sip(
            client.request(body.method.upper(), body.target, **kwargs)
        )

    return app


app = create_app()
