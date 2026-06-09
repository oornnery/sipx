from pathlib import Path
from types import SimpleNamespace
import tomllib

import pytest

from sipx.cli.main import main
from sipx.sip import HeaderMap, SipResponse
from sipx.sip.transport import SipWireDirection, SipWireEvent


def test_pyproject_defines_installable_sipx_console_script() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"]["sipx"] == "sipx.cli.main:main"
    assert pyproject["build-system"]["build-backend"] == "hatchling.build"


def test_cli_runs_python_scenario_file(tmp_path: Path, capsys) -> None:
    scenario_file = tmp_path / "sample_scenario.py"
    scenario_file.write_text(
        "from sipx import scenario\n"
        "@scenario('sample')\n"
        "async def scenario(h):\n"
        "    h.metrics.increment('calls', 1)\n",
        encoding="utf-8",
    )

    code = main(
        [
            "scenario",
            "run",
            str(scenario_file),
            "--artifacts-dir",
            str(tmp_path / "artifacts"),
        ]
    )

    output = capsys.readouterr().out
    assert code == 0
    assert "passed" in output


def test_cli_exports_recorded_scenario_from_timeline(tmp_path: Path, capsys) -> None:
    timeline = tmp_path / "timeline.jsonl"
    timeline.write_text(
        '{"actor_id":"alice","call_id":null,"category":"sip","data":{"method":"INVITE"},'
        '"leg_id":null,"name":"request_sent","run_id":"run-1","ts_ns":1}\n',
        encoding="utf-8",
    )

    code = main(["scenario", "export", str(timeline), "--name", "recorded"])

    output = capsys.readouterr().out
    assert code == 0
    assert "@scenario('recorded')" in output
    assert "request_sent" in output


def test_cli_replays_timeline_as_text_report(tmp_path: Path, capsys) -> None:
    timeline = tmp_path / "timeline.jsonl"
    timeline.write_text(
        '{"actor_id":"alice","call_id":null,"category":"sip","data":{"status":200},'
        '"leg_id":null,"name":"response_received","run_id":"run-2","ts_ns":1}\n',
        encoding="utf-8",
    )

    code = main(["replay", str(timeline)])

    output = capsys.readouterr().out
    assert code == 0
    assert "sipx report: run-2" in output
    assert "sip.response_received" in output


def test_cli_lists_and_shows_profiles(tmp_path: Path, capsys) -> None:
    config = _write_profile_config(tmp_path)

    list_code = main(["profile", "list", "--config", str(config)])
    list_output = capsys.readouterr().out

    show_code = main(["profile", "show", "demo", "--config", str(config)])
    show_output = capsys.readouterr().out

    assert list_code == 0
    assert "demo\tlab\tnative" in list_output
    assert show_code == 0
    assert "name: demo" in show_output
    assert "aor: sip:alice@example.com" in show_output
    assert "remote: 198.51.100.10:5070" in show_output


def test_cli_registers_phone_from_profile(tmp_path: Path, monkeypatch, capsys) -> None:
    config_path = _write_profile_config(tmp_path)
    created = {}

    class FakeSoftphone:
        def __init__(self, config) -> None:
            created["config"] = config
            self.contact = "sip:alice@127.0.0.1:45000"
            self.local_address = ("127.0.0.1", 45000)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

        async def register(self):
            return SimpleNamespace(value="registered")

    monkeypatch.setattr("sipx.cli.main.NativeSoftphone", FakeSoftphone)

    code = main(["phone", "register", "demo", "--config", str(config_path)])

    output = capsys.readouterr().out
    phone_config = created["config"]
    assert code == 0
    assert "registered: registered" in output
    assert str(phone_config.account.aor) == "sip:alice@example.com"
    assert str(phone_config.account.registrar) == "sip:example.com"
    assert phone_config.account.username == "alice"
    assert phone_config.account.password == "secret"
    assert phone_config.remote == ("198.51.100.10", 5070)
    assert phone_config.mode == "lab"


def test_cli_register_requires_profile_or_account_args(monkeypatch, capsys) -> None:
    def fail_if_network_starts(config):
        raise AssertionError("NativeSoftphone must not be constructed")

    monkeypatch.setattr("sipx.cli.main.NativeSoftphone", fail_if_network_starts)

    code = main(["register"])

    captured = capsys.readouterr()
    assert code == 1
    assert "requires a profile or explicit --aor and --registrar" in captured.err
    assert "timed out" not in captured.err


def test_cli_register_uses_registrar_as_default_remote(monkeypatch, capsys) -> None:
    created = {}

    class FakeSoftphone:
        def __init__(self, config) -> None:
            created["config"] = config
            self.contact = "sip:alice@127.0.0.1:45000"
            self.local_address = ("127.0.0.1", 45000)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

        async def register(self):
            return SimpleNamespace(value="registered")

    monkeypatch.setattr("sipx.cli.main.NativeSoftphone", FakeSoftphone)

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
    assert created["config"].remote == ("pbx.example.com", 5070)
    assert "registered: registered" in capsys.readouterr().out


def test_cli_register_help_shows_account_flags(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["register", "--help"])

    output = capsys.readouterr().out
    assert exc_info.value.code == 0
    assert "--aor" in output
    assert "--registrar" in output
    assert "examples:" in output


def test_cli_options_sends_sip_request_without_profile(monkeypatch, capsys) -> None:
    created = {}

    class FakeNativeSipBackend:
        def __init__(self, **kwargs) -> None:
            created["backend_kwargs"] = kwargs
            self.local_address = ("127.0.0.1", 45000)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

        async def send_request(self, request, remote) -> None:
            created["request"] = request
            created["remote"] = remote

        async def receive_event(self, *, timeout=None):
            headers = HeaderMap()
            headers.add("Call-ID", created["request"].headers.get("Call-ID"))
            headers.add("CSeq", created["request"].headers.get("CSeq"))
            return SimpleNamespace(
                message=SipResponse(status_code=200, reason="OK", headers=headers)
            )

    monkeypatch.setattr("sipx.cli.main.NativeSipBackend", FakeNativeSipBackend)

    code = main(["options", "sip:pbx.example.com", "--from", "sip:alice@example.com"])

    request = created["request"]
    assert code == 0
    assert request.method == "OPTIONS"
    assert str(request.uri) == "sip:pbx.example.com"
    assert request.headers.get("From").startswith("<sip:alice@example.com>;tag=")
    assert request.headers.get("To") == "<sip:pbx.example.com>"
    assert created["remote"] == ("pbx.example.com", 5060)
    assert "< 200 OK" in capsys.readouterr().out


def test_cli_message_sends_text_body_and_headers(monkeypatch, capsys) -> None:
    created = {}

    class FakeNativeSipBackend:
        def __init__(self, **kwargs) -> None:
            self.local_address = ("127.0.0.1", 45001)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

        async def send_request(self, request, remote) -> None:
            created["request"] = request
            created["remote"] = remote

        async def receive_event(self, *, timeout=None):
            headers = HeaderMap()
            headers.add("Call-ID", created["request"].headers.get("Call-ID"))
            headers.add("CSeq", created["request"].headers.get("CSeq"))
            return SimpleNamespace(
                message=SipResponse(status_code=202, reason="Accepted", headers=headers)
            )

    monkeypatch.setattr("sipx.cli.main.NativeSipBackend", FakeNativeSipBackend)

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

    request = created["request"]
    assert code == 0
    assert request.method == "MESSAGE"
    assert request.body == b"hello"
    assert request.headers.get("Content-Type") == "text/plain"
    assert request.headers.get("X-Test") == "yes"
    assert created["remote"] == ("example.com", 5060)
    assert "< 202 Accepted" in capsys.readouterr().out


def test_cli_generic_request_supports_data_and_include(monkeypatch, capsys) -> None:
    created = {}

    class FakeNativeSipBackend:
        def __init__(self, **kwargs) -> None:
            self.local_address = ("127.0.0.1", 45002)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

        async def send_request(self, request, remote) -> None:
            created["request"] = request

        async def receive_event(self, *, timeout=None):
            headers = HeaderMap()
            headers.add("Call-ID", created["request"].headers.get("Call-ID"))
            headers.add("CSeq", created["request"].headers.get("CSeq"))
            headers.add("X-Reply", "yes")
            return SimpleNamespace(
                message=SipResponse(
                    status_code=200,
                    reason="OK",
                    headers=headers,
                    body=b"pong",
                )
            )

    monkeypatch.setattr("sipx.cli.main.NativeSipBackend", FakeNativeSipBackend)

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

    request = created["request"]
    output = capsys.readouterr().out
    assert code == 0
    assert request.method == "INFO"
    assert request.body == b"Signal=1"
    assert "X-Reply: yes" in output
    assert output.endswith("pong")


def test_cli_request_retries_digest_challenge(monkeypatch, capsys) -> None:
    requests = []
    receives = 0

    class FakeNativeSipBackend:
        def __init__(self, **kwargs) -> None:
            self.local_address = ("127.0.0.1", 45003)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

        async def send_request(self, request, remote) -> None:
            requests.append(request)

        async def receive_event(self, *, timeout=None):
            nonlocal receives
            receives += 1
            request = requests[-1]
            headers = HeaderMap()
            headers.add("Call-ID", request.headers.get("Call-ID"))
            headers.add("CSeq", request.headers.get("CSeq"))
            if receives == 1:
                headers.add(
                    "Proxy-Authenticate",
                    'Digest realm="example.com", nonce="nonce-1", qop="auth"',
                )
                return SimpleNamespace(
                    message=SipResponse(
                        status_code=407,
                        reason="Proxy Authentication Required",
                        headers=headers,
                    )
                )
            if receives == 2:
                first_request = requests[0]
                headers = HeaderMap()
                headers.add("Call-ID", first_request.headers.get("Call-ID"))
                headers.add("CSeq", first_request.headers.get("CSeq"))
                headers.add(
                    "Proxy-Authenticate",
                    'Digest realm="example.com", nonce="nonce-1", qop="auth"',
                )
                return SimpleNamespace(
                    message=SipResponse(
                        status_code=407,
                        reason="Proxy Authentication Required",
                        headers=headers,
                    )
                )
            return SimpleNamespace(
                message=SipResponse(status_code=200, reason="OK", headers=headers)
            )

    monkeypatch.setattr("sipx.cli.main.NativeSipBackend", FakeNativeSipBackend)

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

    first, second = requests
    assert code == 0
    assert receives == 3
    assert first.headers.get("Proxy-Authorization") is None
    assert second.headers.get("CSeq") == "2 OPTIONS"
    authorization = second.headers.get("Proxy-Authorization") or ""
    assert 'username="alice"' in authorization
    assert 'nonce="nonce-1"' in authorization
    assert "secret-password" not in authorization
    assert "< 200 OK" in capsys.readouterr().out


def test_cli_request_debug_sip_prints_redacted_packets(monkeypatch, capsys) -> None:
    class FakeNativeSipBackend:
        def __init__(self, **kwargs) -> None:
            self.local_address = ("127.0.0.1", 45004)
            self.wire_event_handler = kwargs["wire_event_handler"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

        async def send_request(self, request, remote) -> None:
            self.wire_event_handler(
                SipWireEvent(
                    direction=SipWireDirection.TX,
                    remote=remote,
                    raw=(
                        b"OPTIONS sip:pbx.example.com SIP/2.0\r\n"
                        b"Proxy-Authorization: secret-password\r\n\r\n"
                    ),
                )
            )
            self.request = request

        async def receive_event(self, *, timeout=None):
            headers = HeaderMap()
            headers.add("Call-ID", self.request.headers.get("Call-ID"))
            headers.add("CSeq", self.request.headers.get("CSeq"))
            response = SipResponse(status_code=200, reason="OK", headers=headers)
            self.wire_event_handler(
                SipWireEvent(
                    direction=SipWireDirection.RX,
                    remote=("203.0.113.10", 5060),
                    raw=response.to_bytes(),
                    message=response,
                )
            )
            return SimpleNamespace(message=response)

    monkeypatch.setattr("sipx.cli.main.NativeSipBackend", FakeNativeSipBackend)

    code = main(
        [
            "options",
            "sip:pbx.example.com",
            "--from",
            "sip:alice@example.com",
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
        raise AssertionError("NativeSipBackend must not be constructed")

    monkeypatch.setattr("sipx.cli.main.NativeSipBackend", fail_if_network_starts)

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


def test_cli_places_top_level_call(monkeypatch, capsys) -> None:
    created = {"hangups": 0}

    class FakeSoftphone:
        def __init__(self, config) -> None:
            created["config"] = config

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

        async def call(self, target):
            created["target"] = target
            return SimpleNamespace(call_id="call-1", remote=("203.0.113.10", 5060))

        async def hangup(self, call) -> None:
            created["hangups"] += 1
            created["hungup_call"] = call.call_id

    monkeypatch.setattr("sipx.cli.main.NativeSoftphone", FakeSoftphone)

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
            "--media-port",
            "41000",
            "--codec",
            "PCMA",
        ]
    )

    output = capsys.readouterr().out
    phone_config = created["config"]
    assert code == 0
    assert created["target"] == "sip:bob@example.com"
    assert created["hangups"] == 1
    assert created["hungup_call"] == "call-1"
    assert str(phone_config.account.aor) == "sip:alice@example.com"
    assert phone_config.remote == ("example.com", 5060)
    assert phone_config.media_host == "192.0.2.10"
    assert phone_config.media_port == 41000
    assert phone_config.codecs == ("PCMA",)
    assert "call confirmed: call-1" in output
    assert "call terminated: call-1" in output


def test_cli_call_debug_sip_passes_wire_handler(monkeypatch, capsys) -> None:
    class FakeNativeSipBackend:
        def __init__(self, **kwargs) -> None:
            self.mode = kwargs["mode"]
            self.wire_event_handler = kwargs["wire_event_handler"]

    class FakeSoftphone:
        def __init__(self, config, *, backend=None) -> None:
            assert backend is not None
            self.wire_event_handler = backend.wire_event_handler

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

        async def call(self, target):
            self.wire_event_handler(
                SipWireEvent(
                    direction=SipWireDirection.TX,
                    remote=("203.0.113.10", 5060),
                    raw=b"INVITE sip:bob@example.com SIP/2.0\r\n"
                    b"Authorization: secret-password\r\n\r\n",
                )
            )
            return SimpleNamespace(call_id="call-1", remote=("203.0.113.10", 5060))

        async def hangup(self, call) -> None:
            return None

    monkeypatch.setattr("sipx.cli.main.NativeSipBackend", FakeNativeSipBackend)
    monkeypatch.setattr("sipx.cli.main.NativeSoftphone", FakeSoftphone)

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


def _write_profile_config(tmp_path: Path) -> Path:
    config = tmp_path / "harness.toml"
    config.write_text(
        "[profiles.demo]\n"
        "mode = 'lab'\n"
        "backend = 'native'\n"
        "[profiles.demo.account]\n"
        "aor = 'sip:alice@example.com'\n"
        "registrar = 'sip:example.com'\n"
        "username = 'alice'\n"
        "password = 'secret'\n"
        "remote_host = '198.51.100.10'\n"
        "remote_port = 5070\n"
        "[profiles.demo.media]\n"
        "codecs = ['PCMU']\n",
        encoding="utf-8",
    )
    return config
