"""RFC 5626 Outbound — Managing Client-Initiated Connections in SIP.

This module implements the Outbound mechanism for SIP user agents that
initiate connections to registrars or proxies and wish to keep those
connections alive for incoming request routing.

Key concepts:
    - Flow token: a unique identifier for a client-initiated connection.
    - Keep-alive: CRLF ping sent periodically to maintain NAT bindings.
    - Connection reuse: reusing an existing flow for outbound requests.

References:
    RFC 5626 - Managing Client-Initiated Connections in the Session
               Initiation Protocol (SIP)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sipx.exceptions import TransportError

if TYPE_CHECKING:
    from sipx.transport.base import Transport


@dataclass(slots=True)
class FlowInfo:
    """Metadata for a single client-initiated connection flow."""

    token: str
    remote: tuple[str, int]
    active: bool = True


class OutboundHandler:
    """Manages client-initiated SIP connections per RFC 5626.

    The handler tracks outbound flows by unique tokens, generates CRLF
    keep-alive pings, and supports connection reuse for multiple requests
    over the same flow.

    Args:
        transport: Optional transport layer for sending keep-alives.
    """

    def __init__(self, transport: Transport | None = None) -> None:
        self._transport = transport
        self._flows: dict[str, FlowInfo] = {}

    # ------------------------------------------------------------------
    # Flow token management
    # ------------------------------------------------------------------

    def generate_flow_token(self) -> str:
        """Generate a unique flow token for a new outbound connection.

        Returns:
            A UUID4-based string identifying the new flow.
        """
        token = uuid.uuid4().hex
        return token

    def register_flow(self, remote: tuple[str, int]) -> str:
        """Register a new outbound flow to *remote* and return its token.

        Args:
            remote: The (host, port) of the remote SIP server.

        Returns:
            The flow token assigned to this connection.
        """
        token = self.generate_flow_token()
        self._flows[token] = FlowInfo(token=token, remote=remote)
        return token

    def get_flow(self, flow_token: str) -> FlowInfo | None:
        """Return the flow info for *flow_token*, or ``None`` if unknown."""
        return self._flows.get(flow_token)

    def close_flow(self, flow_token: str) -> None:
        """Mark the flow identified by *flow_token* as inactive.

        Raises:
            TransportError: If the flow token is not registered.
        """
        flow = self._flows.get(flow_token)
        if flow is None:
            raise TransportError(
                f"Unknown flow token: {flow_token}",
                rfc_ref="RFC 5626 §4",
            )
        flow.active = False

    @property
    def active_flows(self) -> list[FlowInfo]:
        """Return all currently active flows."""
        return [f for f in self._flows.values() if f.active]

    # ------------------------------------------------------------------
    # Keep-alive
    # ------------------------------------------------------------------

    @staticmethod
    def generate_keepalive() -> bytes:
        """Return the CRLF keep-alive ping defined by RFC 5626 §4.4.

        The keep-alive consists of a double CRLF sequence (``\\r\\n\\r\\n``)
        which is sent over the connection to maintain NAT bindings and
        detect connection failures.

        Returns:
            The raw bytes ``b'\\r\\n\\r\\n'``.
        """
        return b"\r\n\r\n"

    async def send_keepalive(self, flow_token: str) -> None:
        """Send a CRLF keep-alive on the flow identified by *flow_token*.

        Args:
            flow_token: The token of the flow to ping.

        Raises:
            TransportError: If the flow is unknown, inactive, or has no
                transport configured.
        """
        flow = self._flows.get(flow_token)
        if flow is None:
            raise TransportError(
                f"Unknown flow token: {flow_token}",
                rfc_ref="RFC 5626 §4.4",
            )
        if not flow.active:
            raise TransportError(
                f"Flow {flow_token} is not active",
                rfc_ref="RFC 5626 §4.4",
            )
        if self._transport is None:
            raise TransportError(
                "No transport configured for keep-alive",
                rfc_ref="RFC 5626 §4.4",
            )
        ping = self.generate_keepalive()
        await self._transport.send(ping, flow.remote)

    # ------------------------------------------------------------------
    # Connection reuse
    # ------------------------------------------------------------------

    def can_reuse(self, flow_token: str) -> bool:
        """Check whether the flow identified by *flow_token* can be reused.

        A flow is reusable when it is registered and still active.

        Args:
            flow_token: The token of the flow to check.

        Returns:
            ``True`` if the flow exists and is active, ``False`` otherwise.
        """
        flow = self._flows.get(flow_token)
        return flow is not None and flow.active

    def find_reusable_flow(self, remote: tuple[str, int]) -> str | None:
        """Find an active flow to *remote* that can be reused.

        Args:
            remote: The (host, port) of the desired remote endpoint.

        Returns:
            The flow token if a matching active flow exists, else ``None``.
        """
        for flow in self._flows.values():
            if flow.active and flow.remote == remote:
                return flow.token
        return None
