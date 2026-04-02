"""Tests for sipx._server module: SIPServer interface tests.

These tests focus on the SIPServer interface and configuration,
not actual network behavior (which requires a real socket).
"""

from __future__ import annotations

from unittest.mock import patch


from sipx.server import SIPServer
from sipx.models._message import Response
from sipx._types import TransportConfig


# ============================================================================
# SIPServer creation
# ============================================================================


class TestSIPServerCreation:
    @patch("sipx.server._sync.UDPTransport")
    def test_defaults(self, mock_udp_cls):
        """SIPServer with default args binds to 0.0.0.0:5060."""
        server = SIPServer()
        assert server.config.local_host == "0.0.0.0"
        assert server.config.local_port == 5060
        assert server._running is False

    @patch("sipx.server._sync.UDPTransport")
    def test_custom_host_port(self, mock_udp_cls):
        server = SIPServer(local_host="192.168.1.1", local_port=5080)
        assert server.config.local_host == "192.168.1.1"
        assert server.config.local_port == 5080

    @patch("sipx.server._sync.UDPTransport")
    def test_custom_config(self, mock_udp_cls):
        config = TransportConfig(local_host="10.0.0.1", local_port=5070)
        server = SIPServer(config=config)
        assert server.config is config

    @patch("sipx.server._sync.UDPTransport")
    def test_default_handlers_registered(self, mock_udp_cls):
        """SIPServer registers default handlers for BYE, CANCEL, OPTIONS."""
        server = SIPServer()
        assert "BYE" in server._handlers
        assert "CANCEL" in server._handlers
        assert "OPTIONS" in server._handlers


# ============================================================================
# register_handler
# ============================================================================


class TestRegisterHandler:
    @patch("sipx.server._sync.UDPTransport")
    def test_adds_custom_handler(self, mock_udp_cls):
        server = SIPServer()

        def my_handler(request, source):
            pass

        server.register_handler("INVITE", my_handler)
        assert "INVITE" in server._handlers
        assert server._handlers["INVITE"] is my_handler

    @patch("sipx.server._sync.UDPTransport")
    def test_uppercases_method(self, mock_udp_cls):
        server = SIPServer()

        def my_handler(request, source):
            pass

        server.register_handler("invite", my_handler)
        assert "INVITE" in server._handlers

    @patch("sipx.server._sync.UDPTransport")
    def test_overrides_default_handler(self, mock_udp_cls):
        server = SIPServer()

        def custom_bye(request, source):
            pass

        server.register_handler("BYE", custom_bye)
        assert server._handlers["BYE"] is custom_bye


# ============================================================================
# start/stop lifecycle
# ============================================================================


class TestServerLifecycle:
    @patch("sipx.server._sync.UDPTransport")
    def test_start_sets_running(self, mock_udp_cls):
        server = SIPServer()
        server.start()
        assert server._running is True
        assert server._thread is not None
        server.stop()

    @patch("sipx.server._sync.UDPTransport")
    def test_stop_clears_running(self, mock_udp_cls):
        server = SIPServer()
        server.start()
        server.stop()
        assert server._running is False

    @patch("sipx.server._sync.UDPTransport")
    def test_stop_when_not_running_is_noop(self, mock_udp_cls):
        server = SIPServer()
        server.stop()  # should not raise
        assert server._running is False


# ============================================================================
# Context manager
# ============================================================================


class TestServerContextManager:
    @patch("sipx.server._sync.UDPTransport")
    def test_context_manager_starts_and_stops(self, mock_udp_cls):
        with SIPServer() as server:
            assert server._running is True
        assert server._running is False

    @patch("sipx.server._sync.UDPTransport")
    def test_context_manager_returns_server(self, mock_udp_cls):
        with SIPServer() as server:
            assert isinstance(server, SIPServer)


# ============================================================================
# Server decorators
# ============================================================================


class TestServerDecorators:
    @patch("sipx.server._sync.UDPTransport")
    def test_handle_decorator_registers_handler(self, mock_udp_cls):
        server = SIPServer(local_host="127.0.0.1", local_port=0)

        @server.handle("SUBSCRIBE")
        def on_subscribe(request, source):
            return Response(200)

        assert "SUBSCRIBE" in server._handlers

    @patch("sipx.server._sync.UDPTransport")
    def test_invite_property_decorator(self, mock_udp_cls):
        server = SIPServer(local_host="127.0.0.1", local_port=0)

        @server.invite()
        def on_invite(request, source):
            return Response(200)

        assert "INVITE" in server._handlers

    @patch("sipx.server._sync.UDPTransport")
    def test_register_property_decorator(self, mock_udp_cls):
        server = SIPServer(local_host="127.0.0.1", local_port=0)

        @server.register()
        def on_register(request, source):
            return Response(200)

        assert "REGISTER" in server._handlers

    @patch("sipx.server._sync.UDPTransport")
    def test_message_property_decorator(self, mock_udp_cls):
        server = SIPServer(local_host="127.0.0.1", local_port=0)

        @server.message()
        def on_message(request, source):
            return Response(200)

        assert "MESSAGE" in server._handlers

    @patch("sipx.server._sync.UDPTransport")
    def test_options_property_decorator(self, mock_udp_cls):
        server = SIPServer(local_host="127.0.0.1", local_port=0)

        @server.options()
        def on_options(request, source):
            return Response(200)

        assert "OPTIONS" in server._handlers

    @patch("sipx.server._sync.UDPTransport")
    def test_multiple_decorators(self, mock_udp_cls):
        server = SIPServer(local_host="127.0.0.1", local_port=0)

        @server.invite()
        def h1(request, source):
            return Response(200)

        @server.bye()
        def h2(request, source):
            return Response(200)

        assert "INVITE" in server._handlers
        assert "BYE" in server._handlers
