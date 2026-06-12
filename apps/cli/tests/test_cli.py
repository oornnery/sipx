from pathlib import Path
from types import SimpleNamespace
from typing import Any
import tomllib

import pytest

from sipx.sip import HeaderMap, SipResponse
from sipx.sip.transport import SipWireDirection, SipWireEvent
from sipx.legacy import SipUserAgent
from sipx_cli.main import main


def _scripted_user_agent(sent_requests: list, response_factory):
    """SipUserAgent subclass without sockets; scripts wire I/O for CLI tests.

    Keeps the real ``request()`` logic (headers, CSeq, Digest retry) under
    test while replacing UDP send/receive with deterministic fakes.
    """

    class ScriptedSipUserAgent(SipUserAgent):
        async def start(self):
            return self

        async def stop(self) -> None:
            return None

        @property
        def local_address(self):
            return ("127.0.0.1", 45000)

        def _send_message(self, message, remote):
            sent_requests.append((message, remote))
            event = SipWireEvent(
                direction=SipWireDirection.TX,
                remote=remote,
                raw=message.to_bytes(),
                message=message,
            )
            return event

        async def receive_event(self, *, timeout=None):
            event = response_factory(sent_requests)
            self._emit_wire_event(event)
            return event

    return ScriptedSipUserAgent


def test_pyproject_defines_installable_sipx_console_script() -> None:
    pyproject = tomllib.loads(
        Path("apps/cli/pyproject.toml").read_text(encoding="utf-8")
    )

    assert pyproject["project"]["scripts"]["sipx"] == "sipx_cli.main:main"
    assert pyproject["build-system"]["build-backend"] == "hatchling.build"
    assert pyproject["project"]["dependencies"] == ["sipx"]


def test_cli_help_is_sip_rtp_only(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    output = capsys.readouterr().out
    assert exc_info.value.code == 0
    assert "register" in output
    assert "options" in output
    assert "request" in output
    assert "scenario" not in output
    assert "profile" not in output
    assert "replay" not in output
    assert "phone" not in output


@pytest.mark.parametrize("command", ["scenario", "profile", "replay", "phone"])
def test_cli_rejects_non_sip_commands(command: str) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([command])

    assert exc_info.value.code == 2


def test_cli_registers_from_account_args(monkeypatch, capsys) -> None:
    created = {}

    class FakeUac:
        def __init__(self, **kwargs) -> None:
            created["kwargs"] = kwargs
            self.contact = "sip:alice@127.0.0.1:45000"
            self.local_address = ("127.0.0.1", 45000)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

        async def register(self):
            return SimpleNamespace(value="registered")

    monkeypatch.setattr("sipx_cli.main.SipUac", FakeUac)

    code = main(
        [
            "register",
            "--aor",
            "sip:alice@example.com",
            "--registrar",
            "sip:example.com",
            "--username",
            "alice",
            "--password",
            "secret",
            "--remote-host",
            "198.51.100.10",
            "--remote-port",
            "5070",
            "--mode",
            "lab",
        ]
    )

    output = capsys.readouterr().out
    uac_kwargs = created["kwargs"]
    assert code == 0
    assert "registered: registered" in output
    assert str(uac_kwargs["aor"]) == "sip:alice@example.com"
    assert str(uac_kwargs["registrar"]) == "sip:example.com"
    assert uac_kwargs["username"] == "alice"
    assert uac_kwargs["password"] == "secret"
    assert uac_kwargs["remote"] == ("198.51.100.10", 5070)
    assert uac_kwargs["mode"] == "lab"


def test_cli_register_requires_account_args(monkeypatch, capsys) -> None:
    def fail_if_network_starts(config):
        raise AssertionError("SipUac must not be constructed")

    monkeypatch.setattr("sipx_cli.main.SipUac", fail_if_network_starts)

    code = main(["register"])

    captured = capsys.readouterr()
    assert code == 1
    assert "requires explicit --aor and --registrar" in captured.err
    assert "timed out" not in captured.err


def test_cli_register_uses_registrar_as_default_remote(monkeypatch, capsys) -> None:
    created = {}

    class FakeUac:
        def __init__(self, **kwargs) -> None:
            created["kwargs"] = kwargs
            self.contact = "sip:alice@127.0.0.1:45000"
            self.local_address = ("127.0.0.1", 45000)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

        async def register(self):
            return SimpleNamespace(value="registered")

    monkeypatch.setattr("sipx_cli.main.SipUac", FakeUac)

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
        ]
    )

    assert code == 0
    assert created["kwargs"]["remote"] == ("pbx.example.com", 5070)
    assert "registered: registered" in capsys.readouterr().out


def test_cli_register_help_shows_account_flags(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["register", "--help"])

    output = capsys.readouterr().out
    assert exc_info.value.code == 0
    assert "--aor" in output
    assert "--registrar" in output
    assert "examples:" in output


def test_cli_options_sends_sip_request(monkeypatch, capsys) -> None:
    sent: list = []

    def respond(requests):
        request, _remote = requests[-1]
        headers = HeaderMap()
        headers.add("Call-ID", request.headers.get("Call-ID"))
        headers.add("CSeq", request.headers.get("CSeq"))
        response = SipResponse(status_code=200, reason="OK", headers=headers)
        return SipWireEvent(
            direction=SipWireDirection.RX,
            remote=("203.0.113.10", 5060),
            raw=response.to_bytes(),
            message=response,
        )

    monkeypatch.setattr(
        "sipx_cli.main.SipUserAgent", _scripted_user_agent(sent, respond)
    )

    code = main(["options", "sip:pbx.example.com", "--from", "sip:alice@example.com"])

    request, remote = sent[0]
    assert code == 0
    assert request.method == "OPTIONS"
    assert str(request.uri) == "sip:pbx.example.com"
    assert request.headers.get("From").startswith("<sip:alice@example.com>;tag=")
    assert request.headers.get("To") == "<sip:pbx.example.com>"
    assert remote == ("pbx.example.com", 5060)
    assert "< 200 OK" in capsys.readouterr().out


def test_cli_message_sends_text_body_and_headers(monkeypatch, capsys) -> None:
    sent: list = []

    def respond(requests):
        request, _remote = requests[-1]
        headers = HeaderMap()
        headers.add("Call-ID", request.headers.get("Call-ID"))
        headers.add("CSeq", request.headers.get("CSeq"))
        response = SipResponse(status_code=202, reason="Accepted", headers=headers)
        return SipWireEvent(
            direction=SipWireDirection.RX,
            remote=("203.0.113.10", 5060),
            raw=response.to_bytes(),
            message=response,
        )

    monkeypatch.setattr(
        "sipx_cli.main.SipUserAgent", _scripted_user_agent(sent, respond)
    )

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

    request, remote = sent[0]
    assert code == 0
    assert request.method == "MESSAGE"
    assert request.body == b"hello"
    assert request.headers.get("Content-Type") == "text/plain"
    assert request.headers.get("X-Test") == "yes"
    assert remote == ("example.com", 5060)
    assert "< 202 Accepted" in capsys.readouterr().out


def test_cli_generic_request_supports_data_and_include(monkeypatch, capsys) -> None:
    sent: list = []

    def respond(requests):
        request, _remote = requests[-1]
        headers = HeaderMap()
        headers.add("Call-ID", request.headers.get("Call-ID"))
        headers.add("CSeq", request.headers.get("CSeq"))
        headers.add("X-Reply", "yes")
        response = SipResponse(
            status_code=200,
            reason="OK",
            headers=headers,
            body=b"pong",
        )
        return SipWireEvent(
            direction=SipWireDirection.RX,
            remote=("203.0.113.10", 5060),
            raw=response.to_bytes(),
            message=response,
        )

    monkeypatch.setattr(
        "sipx_cli.main.SipUserAgent", _scripted_user_agent(sent, respond)
    )

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

    request, _remote = sent[0]
    output = capsys.readouterr().out
    assert code == 0
    assert request.method == "INFO"
    assert request.body == b"Signal=1"
    assert "X-Reply: yes" in output
    assert output.endswith("pong")


def test_cli_request_retries_digest_challenge(monkeypatch, capsys) -> None:
    sent: list = []
    receives = 0

    def respond(requests):
        nonlocal receives
        receives += 1
        request, _remote = requests[-1]
        headers = HeaderMap()
        headers.add("Call-ID", request.headers.get("Call-ID"))
        headers.add("CSeq", request.headers.get("CSeq"))
        if receives == 1:
            headers.add(
                "Proxy-Authenticate",
                'Digest realm="example.com", nonce="nonce-1", qop="auth"',
            )
            response = SipResponse(
                status_code=407,
                reason="Proxy Authentication Required",
                headers=headers,
            )
        else:
            response = SipResponse(status_code=200, reason="OK", headers=headers)
        return SipWireEvent(
            direction=SipWireDirection.RX,
            remote=("203.0.113.10", 5060),
            raw=response.to_bytes(),
            message=response,
        )

    monkeypatch.setattr(
        "sipx_cli.main.SipUserAgent", _scripted_user_agent(sent, respond)
    )

    code = main(
        [
            "request",
            "OPTIONS",
            "sip:pbx.example.com",
            "--from",
            "sip:alice@example.com",
            "--username",
            "alice",
            "--password",
            "secret-password",
        ]
    )

    first = sent[0][0]
    second = sent[1][0]
    assert code == 0
    assert receives == 2
    assert first.headers.get("Proxy-Authorization") is None
    assert second.headers.get("CSeq") == "2 OPTIONS"
    authorization = second.headers.get("Proxy-Authorization") or ""
    assert 'username="alice"' in authorization
    assert 'nonce="nonce-1"' in authorization
    assert "secret-password" not in authorization
    assert "< 200 OK" in capsys.readouterr().out


def test_cli_request_debug_sip_prints_redacted_packets(monkeypatch, capsys) -> None:
    sent: list = []
    receives = 0

    def respond(requests):
        nonlocal receives
        receives += 1
        request, _remote = requests[-1]
        headers = HeaderMap()
        headers.add("Call-ID", request.headers.get("Call-ID"))
        headers.add("CSeq", request.headers.get("CSeq"))
        if receives == 1:
            headers.add(
                "Proxy-Authenticate",
                'Digest realm="example.com", nonce="nonce-1", qop="auth"',
            )
            response = SipResponse(
                status_code=407,
                reason="Proxy Authentication Required",
                headers=headers,
            )
        else:
            response = SipResponse(status_code=200, reason="OK", headers=headers)
        return SipWireEvent(
            direction=SipWireDirection.RX,
            remote=("203.0.113.10", 5060),
            raw=response.to_bytes(),
            message=response,
        )

    monkeypatch.setattr(
        "sipx_cli.main.SipUserAgent", _scripted_user_agent(sent, respond)
    )

    code = main(
        [
            "options",
            "sip:pbx.example.com",
            "--from",
            "sip:alice@example.com",
            "--username",
            "alice",
            "--password",
            "secret-password",
            "--debug-sip",
        ]
    )

    captured = capsys.readouterr()
    assert code == 0
    assert "--- SIP TX pbx.example.com:5060" in captured.err
    assert "--- SIP RX 203.0.113.10:5060" in captured.err
    assert "Proxy-Authorization: [REDACTED]" in captured.err
    assert "secret-password" not in captured.err


def test_cli_request_requires_from_identity(monkeypatch, capsys) -> None:
    def fail_if_network_starts(**kwargs):
        raise AssertionError("SipUserAgent must not be constructed")

    monkeypatch.setattr("sipx_cli.main.SipUserAgent", fail_if_network_starts)

    code = main(["options", "sip:pbx.example.com"])

    captured = capsys.readouterr()
    assert code == 1
    assert "requires --from/--aor" in captured.err


def test_cli_request_help_shows_curl_like_flags(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["request", "--help"])

    output = capsys.readouterr().out
    assert exc_info.value.code == 0
    assert "-H" in output
    assert "--data" in output
    assert "--body-file" in output
    assert "examples:" in output


def test_cli_call_help_shows_dtmf_flag(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["call", "--help"])

    output = capsys.readouterr().out
    assert exc_info.value.code == 0
    assert "--dtmf" in output
    assert "--dtmf-duration-ms" in output
    assert "--audio" in output
    assert "--rtp-bind" in output
    assert "--rtp-advertise" in output
    assert "--jitter-buffer-ms" in output
    assert "--rtp-stats" in output
    assert "--metrics-json" in output


def test_cli_places_top_level_call(monkeypatch, tmp_path: Path, capsys) -> None:
    created: dict[str, Any] = {"hangups": 0}
    metrics_path = tmp_path / "metrics.json"

    class FakeUac:
        def __init__(self, **kwargs) -> None:
            created["kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

        async def call(self, target, *, audio="none"):
            created["target"] = target
            created["audio"] = audio
            return SimpleNamespace(
                call_id="call-1",
                remote=("203.0.113.10", 5060),
                state=SimpleNamespace(value="confirmed"),
                local_sdp=None,
                remote_sdp=None,
            )

        async def hangup(self, call) -> None:
            created["hangups"] += 1
            created["hungup_call"] = call.call_id

        def rtp_session(self, call):
            return None

    monkeypatch.setattr("sipx_cli.main.SipUac", FakeUac)

    code = main(
        [
            "call",
            "sip:bob@example.com",
            "--aor",
            "sip:alice@example.com",
            "--registrar",
            "sip:example.com",
            "--duration",
            "0",
            "--media-host",
            "192.0.2.10",
            "--rtp-bind",
            "127.0.0.1",
            "--rtp-advertise",
            "192.0.2.20",
            "--media-port",
            "41000",
            "--codec",
            "PCMA",
            "--audio",
            "noise",
            "--jitter-buffer-ms",
            "120",
            "--rtp-stats",
            "--metrics-json",
            str(metrics_path),
        ]
    )

    output = capsys.readouterr().out
    uac_kwargs = created["kwargs"]
    assert code == 0
    assert created["target"] == "sip:bob@example.com"
    assert created["audio"] == "noise"
    assert created["hangups"] == 1
    assert created["hungup_call"] == "call-1"
    assert str(uac_kwargs["aor"]) == "sip:alice@example.com"
    assert uac_kwargs["remote"] == ("example.com", 5060)
    assert uac_kwargs["media_host"] == "192.0.2.10"
    assert uac_kwargs["rtp_bind_host"] == "127.0.0.1"
    assert uac_kwargs["rtp_advertise_host"] == "192.0.2.20"
    assert uac_kwargs["media_port"] == 41000
    assert uac_kwargs["jitter_buffer_ms"] == 120
    assert uac_kwargs["codecs"] == ("PCMA",)
    assert "call confirmed: call-1" in output
    assert "call terminated: call-1" in output
    assert "rtp: none" in output
    assert '"call_id": "call-1"' in metrics_path.read_text(encoding="utf-8")


def test_cli_call_debug_sip_passes_wire_handler(monkeypatch, capsys) -> None:
    class FakeUac:
        def __init__(self, **kwargs) -> None:
            self.wire_event_handler = kwargs["event_hooks"]["wire"][0]

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

        async def call(self, target, *, audio="none"):
            self.wire_event_handler(
                SipWireEvent(
                    direction=SipWireDirection.TX,
                    remote=("203.0.113.10", 5060),
                    raw=b"INVITE sip:bob@example.com SIP/2.0\r\n"
                    b"Authorization: secret-password\r\n\r\n",
                )
            )
            return SimpleNamespace(
                call_id="call-1",
                remote=("203.0.113.10", 5060),
                state=SimpleNamespace(value="confirmed"),
                local_sdp=None,
                remote_sdp=None,
            )

        async def hangup(self, call) -> None:
            return None

        def rtp_session(self, call):
            return None

    monkeypatch.setattr("sipx_cli.main.SipUac", FakeUac)

    code = main(
        [
            "call",
            "sip:bob@example.com",
            "--aor",
            "sip:alice@example.com",
            "--registrar",
            "sip:example.com",
            "--duration",
            "0",
            "--debug-sip",
        ]
    )

    captured = capsys.readouterr()
    assert code == 0
    assert "--- SIP TX 203.0.113.10:5060" in captured.err
    assert "Authorization: [REDACTED]" in captured.err
    assert "secret-password" not in captured.err
