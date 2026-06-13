"""Tests for the sipx FastAPI REST service."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sipx import Response
from sipx_fastapi.app import create_app
from sipx_fastapi.config import Settings


class FakeAsyncClient:
    """In-memory AsyncClient double for FastAPI route tests."""

    instances: list["FakeAsyncClient"] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.calls: list[tuple[str, tuple, dict]] = []
        FakeAsyncClient.instances.append(self)

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def options(self, uri: str, **kwargs: Any) -> Response:
        self.calls.append(("options", (uri,), kwargs))
        return Response(
            status_code=200, reason="OK", headers={"Allow": "INVITE, ACK, BYE"}
        )

    async def register(self, uri: str, **kwargs: Any) -> Response:
        self.calls.append(("register", (uri,), kwargs))
        return Response(
            status_code=200,
            reason="OK",
            headers={"Expires": kwargs.get("Expires", "3600")},
        )

    async def message(self, uri: str, body: Any, **kwargs: Any) -> Response:
        self.calls.append(("message", (uri, body), kwargs))
        return Response(status_code=202, reason="Accepted", headers={})

    async def request(self, method: str, uri: str, **kwargs: Any) -> Response:
        self.calls.append(("request", (method, uri), kwargs))
        return Response(status_code=200, reason="OK", headers={})


@pytest.fixture
def settings() -> Settings:
    return Settings(
        aor="sip:1001@example.com",
        registrar="sip:pbx.example.com:5060",
        username="1001",
        password="secret",
        local_host="0.0.0.0",
        local_port=0,
        timeout=5.0,
        transport="udp",
        user_agent="sipx-fastapi/test",
        host="127.0.0.1",
        port=8000,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    fake = FakeAsyncClient()
    app = create_app(settings=settings, client=fake)
    with TestClient(app) as test_client:
        test_client.app.state.fake_client = fake  # type: ignore[attr-defined]
        yield test_client


def test_health_reports_sip_config(client: TestClient, settings: Settings) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["sip"]["aor"] == settings.aor
    assert payload["sip"]["auth_configured"] is True


def test_options_endpoint(client: TestClient) -> None:
    response = client.post("/sip/options", json={"target": "sip:pbx.example.com"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status_code"] == 200
    fake: FakeAsyncClient = client.app.state.fake_client  # type: ignore[attr-defined]
    assert fake.calls[0][0] == "options"


def test_register_endpoint(client: TestClient, settings: Settings) -> None:
    response = client.post("/sip/register", json={"expires": 120})
    assert response.status_code == 200
    fake: FakeAsyncClient = client.app.state.fake_client  # type: ignore[attr-defined]
    assert fake.calls[-1] == ("register", (settings.registrar,), {"Expires": "120"})


def test_unregister_endpoint(client: TestClient, settings: Settings) -> None:
    response = client.post("/sip/unregister", json={})
    assert response.status_code == 200
    fake: FakeAsyncClient = client.app.state.fake_client  # type: ignore[attr-defined]
    assert fake.calls[-1] == ("register", (settings.registrar,), {"Expires": "0"})


def test_message_endpoint(client: TestClient) -> None:
    response = client.post(
        "/sip/message",
        json={"target": "sip:1002@example.com", "text": "hello"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status_code"] == 202
    fake: FakeAsyncClient = client.app.state.fake_client  # type: ignore[attr-defined]
    assert fake.calls[-1][0] == "message"


def test_generic_request_endpoint(client: TestClient) -> None:
    response = client.post(
        "/sip/request",
        json={
            "method": "INFO",
            "target": "sip:1002@example.com",
            "headers": {"Content-Type": "application/dtmf-relay"},
            "body": "Signal=1\r\nDuration=160\r\n",
        },
    )
    assert response.status_code == 200
    fake: FakeAsyncClient = client.app.state.fake_client  # type: ignore[attr-defined]
    method, uri = fake.calls[-1][1]
    assert method == "INFO"
    assert uri == "sip:1002@example.com"
