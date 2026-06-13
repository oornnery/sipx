from pathlib import Path
from typing import Any
import tomllib

import pytest

from sipx import Request, Response
from sipx_cli.main import main


class FakeAsyncClient:
    """In-memory AsyncClient double that records calls and returns responses."""

    instances: list["FakeAsyncClient"] = []
    responses: list[Response] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.calls: list[tuple[str, tuple, dict]] = []
        FakeAsyncClient.instances.append(self)

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def _next_response(self) -> Response:
        if FakeAsyncClient.responses:
            return FakeAsyncClient.responses.pop(0)
        return Response(status_code=200, reason="OK", headers={})

    async def options(self, uri: str, **kwargs: Any) -> Response:
        self.calls.append(("options", (uri,), kwargs))
        return await self._respond(uri, "OPTIONS", kwargs)

    async def message(self, uri: str, body: Any, **kwargs: Any) -> Response:
        self.calls.append(("message", (uri, body), kwargs))
        return await self._respond(uri, "MESSAGE", kwargs)

    async def register(self, uri: str, **kwargs: Any) -> Response:
        self.calls.append(("register", (uri,), kwargs))
        return await self._respond(uri, "REGISTER", kwargs)

    async def request(self, method: str, uri: str, **kwargs: Any) -> Response:
        self.calls.append(("request", (method, uri), kwargs))
        return await self._respond(uri, method, kwargs)

    async def _respond(self, uri: str, method: str, kwargs: dict) -> Response:
        request = Request(method=method, uri=uri, headers=dict(kwargs))
        for hook in (self.kwargs.get("event_hooks") or {}).get("request", []):
            hook(request)
        response = self._next_response()
        response.request = request
        for hook in (self.kwargs.get("event_hooks") or {}).get("response", []):
            hook(response)
        return response


@pytest.fixture(autouse=True)
def fake_client(monkeypatch):
    FakeAsyncClient.instances = []
    FakeAsyncClient.responses = []
    monkeypatch.setattr("sipx_cli.main.AsyncClient", FakeAsyncClient)
    return FakeAsyncClient


def test_pyproject_defines_installable_sipx_console_script() -> None:
    pyproject = tomllib.loads(
        Path("apps/cli/pyproject.toml").read_text(encoding="utf-8")
    )

    assert pyproject["project"]["scripts"]["sipx"] == "sipx_cli.main:main"
    assert pyproject["build-system"]["build-backend"] == "hatchling.build"
    assert pyproject["project"]["dependencies"] == ["sipx"]


def test_cli_help_lists_async_client_commands(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    output = capsys.readouterr().out
    assert exc_info.value.code == 0
    assert "register" in output
    assert "options" in output
    assert "request" in output
    assert "message" in output
    assert "call" not in output.split()
    assert "listen" not in output.split()


@pytest.mark.parametrize("command", ["scenario", "profile", "replay", "phone", "call"])
def test_cli_rejects_removed_commands(command: str) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([command])

    assert exc_info.value.code == 2


def test_cli_options_sends_request(capsys) -> None:
    code = main(["options", "sip:pbx.example.com", "--from", "sip:alice@example.com"])

    client = FakeAsyncClient.instances[0]
    assert code == 0
    assert client.calls == [("options", ("sip:pbx.example.com",), {})]
    assert client.kwargs["config"].from_uri == "sip:alice@example.com"
    output = capsys.readouterr().out
    assert "> OPTIONS sip:pbx.example.com" in output
    assert "< 200 OK" in output


def test_cli_options_requires_from_identity(capsys) -> None:
    code = main(["options", "sip:pbx.example.com"])

    captured = capsys.readouterr()
    assert code == 1
    assert "requires --from/--aor" in captured.err
    assert FakeAsyncClient.instances == []


def test_cli_message_sends_text_body_and_headers(capsys) -> None:
    FakeAsyncClient.responses = [
        Response(status_code=202, reason="Accepted", headers={})
    ]

    code = main(
        [
            "message",
            "sip:bob@example.com",
            "hello",
            "--from",
            "sip:alice@example.com",
            "-H",
            "X-Test: yes",
        ]
    )

    client = FakeAsyncClient.instances[0]
    name, args, kwargs = client.calls[0]
    assert code == 0
    assert name == "message"
    assert args == ("sip:bob@example.com", b"hello")
    assert kwargs["X-Test"] == "yes"
    assert "< 202 Accepted" in capsys.readouterr().out


def test_cli_generic_request_supports_data_and_include(capsys) -> None:
    FakeAsyncClient.responses = [
        Response(
            status_code=200,
            reason="OK",
            headers={"X-Reply": "yes"},
            body=b"pong",
        )
    ]

    code = main(
        [
            "request",
            "INFO",
            "sip:bob@example.com",
            "--from",
            "sip:alice@example.com",
            "-H",
            "Content-Type: application/dtmf-relay",
            "-d",
            "Signal=1",
            "--include",
        ]
    )

    client = FakeAsyncClient.instances[0]
    name, args, kwargs = client.calls[0]
    output = capsys.readouterr().out
    assert code == 0
    assert name == "request"
    assert args == ("INFO", "sip:bob@example.com")
    assert kwargs["body"] == b"Signal=1"
    assert kwargs["Content-Type"] == "application/dtmf-relay"
    assert "X-Reply: yes" in output
    assert output.endswith("pong")


def test_cli_request_rejects_multiple_body_sources(capsys, tmp_path: Path) -> None:
    body_file = tmp_path / "body.txt"
    body_file.write_text("data")

    code = main(
        [
            "request",
            "INFO",
            "sip:bob@example.com",
            "--from",
            "sip:alice@example.com",
            "-d",
            "Signal=1",
            "--body-file",
            str(body_file),
        ]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "only one request body source" in captured.err


def test_cli_request_returns_failure_on_error_response(capsys) -> None:
    FakeAsyncClient.responses = [
        Response(status_code=486, reason="Busy Here", headers={})
    ]

    code = main(
        [
            "request",
            "OPTIONS",
            "sip:pbx.example.com",
            "--from",
            "sip:alice@example.com",
        ]
    )

    assert code == 1
    assert "< 486 Busy Here" in capsys.readouterr().out


def test_cli_register_sends_expires_and_auth(capsys) -> None:
    code = main(
        [
            "register",
            "--aor",
            "sip:alice@example.com",
            "--registrar",
            "sip:pbx.example.com:5070",
            "--username",
            "alice",
            "--password",
            "secret",
            "--expires",
            "600",
        ]
    )

    client = FakeAsyncClient.instances[0]
    name, args, kwargs = client.calls[0]
    assert code == 0
    assert name == "register"
    assert args == ("sip:pbx.example.com:5070",)
    assert kwargs["Expires"] == "600"
    assert client.kwargs["auth"] is not None
    assert client.kwargs["auth"].username == "alice"
    assert "registered: 200 OK" in capsys.readouterr().out


def test_cli_register_requires_account_args(capsys) -> None:
    code = main(["register"])

    captured = capsys.readouterr()
    assert code == 1
    assert "requires explicit --aor and --registrar" in captured.err
    assert FakeAsyncClient.instances == []


def test_cli_register_reports_failure_status(capsys) -> None:
    FakeAsyncClient.responses = [
        Response(status_code=403, reason="Forbidden", headers={})
    ]

    code = main(
        [
            "register",
            "--aor",
            "sip:alice@example.com",
            "--registrar",
            "sip:pbx.example.com",
        ]
    )

    assert code == 1
    assert "registered failed: 403 Forbidden" in capsys.readouterr().out


def test_cli_unregister_sends_expires_zero(capsys) -> None:
    code = main(
        [
            "unregister",
            "--aor",
            "sip:alice@example.com",
            "--registrar",
            "sip:pbx.example.com",
        ]
    )

    client = FakeAsyncClient.instances[0]
    _name, _args, kwargs = client.calls[0]
    assert code == 0
    assert kwargs["Expires"] == "0"
    assert "unregistered: 200 OK" in capsys.readouterr().out


def test_cli_register_help_shows_account_flags(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["register", "--help"])

    output = capsys.readouterr().out
    assert exc_info.value.code == 0
    assert "--aor" in output
    assert "--registrar" in output
    assert "examples:" in output


def test_cli_request_help_shows_curl_like_flags(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["request", "--help"])

    output = capsys.readouterr().out
    assert exc_info.value.code == 0
    assert "-H" in output
    assert "--data" in output
    assert "--body-file" in output
    assert "examples:" in output


def test_cli_debug_sip_prints_redacted_messages(capsys) -> None:
    FakeAsyncClient.responses = [
        Response(
            status_code=200,
            reason="OK",
            headers={"Authorization": 'Digest username="alice"'},
        )
    ]

    code = main(
        [
            "request",
            "OPTIONS",
            "sip:pbx.example.com",
            "--from",
            "sip:alice@example.com",
            "-H",
            "Proxy-Authorization: Digest password-ish secret-password",
            "--debug-sip",
        ]
    )

    captured = capsys.readouterr()
    assert code == 0
    assert "--- SIP TX sip:pbx.example.com ---" in captured.err
    assert "--- SIP RX 200 OK ---" in captured.err
    assert "Proxy-Authorization: [REDACTED]" in captured.err
    assert "Authorization: [REDACTED]" in captured.err
    assert "secret-password" not in captured.err
