"""Tests for RFC 5626 Outbound connection management in sipx.rfc.outbound."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Literal
from unittest.mock import AsyncMock

import pytest

from sipx.exceptions import TransportError
from sipx.rfc.outbound import FlowInfo, OutboundHandler
from sipx.transport.base import Transport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeTransport(Transport):
    """Minimal concrete Transport for testing."""

    def __init__(self) -> None:
        self.sent: list[tuple[bytes, tuple[str, int]]] = []

    async def send(self, data: bytes, remote: tuple[str, int]) -> None:
        self.sent.append((data, remote))

    async def receive(self) -> AsyncIterator[tuple[bytes, tuple[str, int]]]:
        yield b"", ("", 0)  # pragma: no cover

    async def close(self) -> None:
        pass

    @property
    def local_address(self) -> tuple[str, int]:
        return ("127.0.0.1", 5060)

    @property
    def transport_type(self) -> Literal["udp", "tcp", "tls"]:
        return "tcp"


# ===========================================================================
# OutboundHandler — Import & Instantiation
# ===========================================================================


class TestOutboundImport:
    """Basic import and instantiation tests."""

    def test_import_outbound_handler(self):
        """OutboundHandler can be imported from sipx.rfc.outbound."""
        from sipx.rfc.outbound import OutboundHandler as OH

        assert OH is not None

    def test_instantiate_handler(self):
        """OutboundHandler can be instantiated without arguments."""
        handler = OutboundHandler()
        assert handler is not None
        assert handler.active_flows == []


# ===========================================================================
# OutboundHandler — Flow Token Generation
# ===========================================================================


class TestFlowTokenGeneration:
    """Tests for flow token generation and uniqueness."""

    def test_generate_flow_token_returns_string(self):
        """generate_flow_token returns a non-empty string."""
        handler = OutboundHandler()
        token = handler.generate_flow_token()
        assert isinstance(token, str)
        assert len(token) > 10

    def test_flow_tokens_are_unique(self):
        """Successive flow tokens are distinct."""
        handler = OutboundHandler()
        token1 = handler.generate_flow_token()
        token2 = handler.generate_flow_token()
        assert token1 != token2

    def test_register_flow_returns_token(self):
        """register_flow returns a token and stores the flow."""
        handler = OutboundHandler()
        token = handler.register_flow(("proxy.example.com", 5060))
        assert isinstance(token, str)
        flow = handler.get_flow(token)
        assert flow is not None
        assert flow.remote == ("proxy.example.com", 5060)
        assert flow.active is True


# ===========================================================================
# OutboundHandler — Keep-alive
# ===========================================================================


class TestKeepAlive:
    """Tests for CRLF keep-alive ping generation."""

    def test_generate_keepalive_returns_crlf(self):
        """generate_keepalive returns the double CRLF sequence."""
        handler = OutboundHandler()
        ping = handler.generate_keepalive()
        assert ping == b"\r\n\r\n"

    @pytest.mark.asyncio
    async def test_send_keepalive_via_transport(self):
        """send_keepalive sends CRLF ping to the flow's remote address."""
        transport = FakeTransport()
        handler = OutboundHandler(transport=transport)
        token = handler.register_flow(("proxy.example.com", 5060))

        await handler.send_keepalive(token)

        assert len(transport.sent) == 1
        assert transport.sent[0] == (b"\r\n\r\n", ("proxy.example.com", 5060))

    @pytest.mark.asyncio
    async def test_send_keepalive_unknown_token_raises(self):
        """send_keepalive raises TransportError for unknown flow token."""
        handler = OutboundHandler()
        with pytest.raises(TransportError, match="Unknown flow"):
            await handler.send_keepalive("nonexistent")

    @pytest.mark.asyncio
    async def test_send_keepalive_no_transport_raises(self):
        """send_keepalive raises TransportError when no transport is set."""
        handler = OutboundHandler()
        token = handler.register_flow(("proxy.example.com", 5060))
        with pytest.raises(TransportError, match="No transport"):
            await handler.send_keepalive(token)


# ===========================================================================
# OutboundHandler — Connection Reuse
# ===========================================================================


class TestConnectionReuse:
    """Tests for connection reuse detection."""

    def test_can_reuse_active_flow(self):
        """can_reuse returns True for an active flow."""
        handler = OutboundHandler()
        token = handler.register_flow(("proxy.example.com", 5060))
        assert handler.can_reuse(token) is True

    def test_cannot_reuse_closed_flow(self):
        """can_reuse returns False after the flow is closed."""
        handler = OutboundHandler()
        token = handler.register_flow(("proxy.example.com", 5060))
        handler.close_flow(token)
        assert handler.can_reuse(token) is False

    def test_find_reusable_flow(self):
        """find_reusable_flow returns the token of a matching active flow."""
        handler = OutboundHandler()
        token = handler.register_flow(("proxy.example.com", 5060))
        found = handler.find_reusable_flow(("proxy.example.com", 5060))
        assert found == token

    def test_find_reusable_flow_none_when_closed(self):
        """find_reusable_flow returns None when the only flow is closed."""
        handler = OutboundHandler()
        token = handler.register_flow(("proxy.example.com", 5060))
        handler.close_flow(token)
        found = handler.find_reusable_flow(("proxy.example.com", 5060))
        assert found is None
