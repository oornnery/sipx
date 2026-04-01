"""Tests for sipx._session_timer (SessionTimer, SessionTimerConfig)."""

from __future__ import annotations

from unittest.mock import MagicMock

from sipx.session import SessionTimer, SessionTimerConfig
from sipx.models._message import Request, Response


class TestSessionTimerConfig:
    def test_defaults(self):
        cfg = SessionTimerConfig()
        assert cfg.interval == 1800
        assert cfg.min_se == 90
        assert cfg.margin == 0.5
        assert cfg.refresher == "uac"
        assert cfg.method == "UPDATE"


class TestSessionTimerParseResponse:
    def _make_timer(self, headers: dict) -> SessionTimer:
        """Create a SessionTimer with a mock response containing given headers."""
        resp = Response(status_code=200, headers=headers)
        # SessionTimer expects response.request but only uses it in _do_refresh
        resp.request = None  # type: ignore[assignment]
        return SessionTimer(client=None, response=resp)  # type: ignore[arg-type]

    def test_parse_session_expires(self):
        timer = self._make_timer({"Session-Expires": "600;refresher=uas"})
        assert timer.config.interval == 600
        assert timer.config.refresher == "uas"

    def test_parse_min_se(self):
        timer = self._make_timer({"Min-SE": "120"})
        assert timer.config.min_se == 120

    def test_enforce_min_se(self):
        timer = self._make_timer(
            {
                "Session-Expires": "60",
                "Min-SE": "90",
            }
        )
        # interval < min_se, so interval should be bumped to min_se
        assert timer.config.interval == 90

    def test_refresh_interval_calculation(self):
        timer = self._make_timer({"Session-Expires": "1800"})
        assert timer.refresh_interval == 1800 * 0.5

    def test_custom_config_margin(self):
        resp = Response(status_code=200)
        resp.request = None  # type: ignore[assignment]
        cfg = SessionTimerConfig(interval=1000, margin=0.75)
        timer = SessionTimer(client=None, response=resp, config=cfg)  # type: ignore[arg-type]
        assert timer.refresh_interval == 1000 * 0.75

    def test_no_session_expires_header(self):
        timer = self._make_timer({})
        # Should use defaults
        assert timer.config.interval == 1800
        assert timer.config.min_se == 90

    def test_parse_session_expires_with_no_refresher(self):
        timer = self._make_timer({"Session-Expires": "900"})
        assert timer.config.interval == 900
        # refresher stays at default
        assert timer.config.refresher == "uac"


class TestSessionTimerStaticMethods:
    def test_add_supported_empty(self):
        req = Request(method="INVITE", uri="sip:bob@example.com")
        SessionTimer.add_supported(req)
        assert req.headers["Supported"] == "timer"

    def test_add_supported_appends(self):
        req = Request(
            method="INVITE",
            uri="sip:bob@example.com",
            headers={"Supported": "replaces"},
        )
        SessionTimer.add_supported(req)
        assert "replaces" in req.headers["Supported"]
        assert "timer" in req.headers["Supported"]

    def test_add_supported_no_duplicate(self):
        req = Request(
            method="INVITE",
            uri="sip:bob@example.com",
            headers={"Supported": "timer"},
        )
        SessionTimer.add_supported(req)
        # Should not add 'timer' again
        assert req.headers["Supported"].count("timer") == 1

    def test_add_session_expires(self):
        req = Request(method="INVITE", uri="sip:bob@example.com")
        SessionTimer.add_session_expires(req, interval=600, refresher="uas")
        assert req.headers["Session-Expires"] == "600;refresher=uas"

    def test_add_session_expires_defaults(self):
        req = Request(method="INVITE", uri="sip:bob@example.com")
        SessionTimer.add_session_expires(req)
        assert req.headers["Session-Expires"] == "1800;refresher=uac"

    def test_add_min_se(self):
        req = Request(method="INVITE", uri="sip:bob@example.com")
        SessionTimer.add_min_se(req, min_se=120)
        assert req.headers["Min-SE"] == "120"

    def test_add_min_se_default(self):
        req = Request(method="INVITE", uri="sip:bob@example.com")
        SessionTimer.add_min_se(req)
        assert req.headers["Min-SE"] == "90"


class TestSessionTimerStartStop:
    def test_start_sets_running(self):
        resp = Response(status_code=200)
        resp.request = None  # type: ignore[assignment]
        timer = SessionTimer(client=None, response=resp)  # type: ignore[arg-type]
        timer.start()
        assert timer.is_running is True
        timer.stop()
        assert timer.is_running is False

    def test_stop_cancels_timer(self):
        resp = Response(status_code=200)
        resp.request = None  # type: ignore[assignment]
        timer = SessionTimer(client=None, response=resp)  # type: ignore[arg-type]
        timer.start()
        timer.stop()
        assert timer._timer is None

    def test_double_start_is_noop(self):
        resp = Response(status_code=200)
        resp.request = None  # type: ignore[assignment]
        timer = SessionTimer(client=None, response=resp)  # type: ignore[arg-type]
        timer.start()
        timer.start()  # should not raise
        assert timer.is_running is True
        timer.stop()

    def test_refresh_count_starts_at_zero(self):
        resp = Response(status_code=200)
        resp.request = None  # type: ignore[assignment]
        timer = SessionTimer(client=None, response=resp)  # type: ignore[arg-type]
        assert timer.refresh_count == 0


class TestSessionTimerDoRefresh:
    def test_do_refresh_when_not_running(self):
        resp = Response(status_code=200)
        resp.request = None  # type: ignore[assignment]
        timer = SessionTimer(client=None, response=resp)  # type: ignore[arg-type]
        timer._running = False
        timer._do_refresh()  # should return early, no error
        assert timer.refresh_count == 0

    def test_do_refresh_no_request(self):
        resp = Response(status_code=200)
        resp.request = None  # type: ignore[assignment]
        timer = SessionTimer(client=None, response=resp)  # type: ignore[arg-type]
        timer._running = True
        timer._do_refresh()  # request is None, should return early
        assert timer.refresh_count == 0
        timer.stop()

    def test_do_refresh_update_method(self):
        req = Request(method="INVITE", uri="sip:bob@example.com")
        resp = Response(status_code=200)
        resp.request = req

        client = MagicMock()
        update_resp = Response(status_code=200)
        client.update.return_value = update_resp

        config = SessionTimerConfig(method="UPDATE")
        timer = SessionTimer(client=client, response=resp, config=config)
        timer._running = True
        timer._do_refresh()
        client.update.assert_called_once()
        assert timer.refresh_count == 1
        timer.stop()

    def test_do_refresh_invite_method(self):
        req = Request(method="INVITE", uri="sip:bob@example.com")
        resp = Response(status_code=200)
        resp.request = req

        client = MagicMock()
        invite_resp = Response(status_code=200)
        client.invite.return_value = invite_resp

        config = SessionTimerConfig(method="INVITE")
        timer = SessionTimer(client=client, response=resp, config=config)
        timer._running = True
        timer._do_refresh()
        client.invite.assert_called_once()
        assert timer.refresh_count == 1
        timer.stop()

    def test_do_refresh_calls_on_refresh_callback(self):
        req = Request(method="INVITE", uri="sip:bob@example.com")
        resp = Response(status_code=200)
        resp.request = req

        client = MagicMock()
        update_resp = Response(status_code=200)
        client.update.return_value = update_resp

        received = []
        timer = SessionTimer(
            client=client,
            response=resp,
            on_refresh=lambda r: received.append(r),
        )
        timer._running = True
        timer._do_refresh()
        assert len(received) == 1
        timer.stop()

    def test_do_refresh_exception_silenced(self):
        req = Request(method="INVITE", uri="sip:bob@example.com")
        resp = Response(status_code=200)
        resp.request = req

        client = MagicMock()
        client.update.side_effect = Exception("connection error")

        timer = SessionTimer(client=client, response=resp)
        timer._running = True
        timer._do_refresh()  # should not raise
        assert timer.refresh_count == 0
        timer.stop()

    def test_schedule_next_when_not_running(self):
        resp = Response(status_code=200)
        resp.request = None  # type: ignore[assignment]
        timer = SessionTimer(client=None, response=resp)  # type: ignore[arg-type]
        timer._running = False
        timer._schedule_next()  # should not create a timer
        assert timer._timer is None
