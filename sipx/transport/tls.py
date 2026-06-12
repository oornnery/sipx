"""SIP over TLS transport using asyncio streams with SSL.

Implements RFC 3261 §26.2 SIPS URI scheme and TLS requirements.
Extends TcpTransport with TLS encryption and certificate validation.
"""

from __future__ import annotations

import asyncio
import ssl
from dataclasses import dataclass
from typing import Literal

from sipx.exceptions import TransportError
from sipx.transport.base import TransportConfig
from sipx.transport.tcp import TcpTransport


@dataclass(frozen=True, slots=True)
class TlsConfig:
    certfile: str | None = None
    keyfile: str | None = None
    ca_certs: str | None = None
    verify_mode: bool = True
    check_hostname: bool = True


class TlsTransport(TcpTransport):
    """SIP over TLS transport using asyncio StreamReader/StreamWriter with SSL.

    Extends TcpTransport with TLS encryption and certificate validation
    per RFC 3261 §26.2 and RFC 5922 domain certificate validation.
    """

    def __init__(
        self,
        config: TransportConfig | None = None,
        tls_config: TlsConfig | None = None,
    ) -> None:
        super().__init__(config)
        self._tls_config = tls_config or TlsConfig()
        self._ssl_context = self._create_ssl_context()

    @property
    def transport_type(self) -> Literal["tls"]:
        """Return the transport protocol identifier."""
        return "tls"

    def _create_ssl_context(self) -> ssl.SSLContext:
        try:
            context = ssl.create_default_context()

            if self._tls_config.check_hostname:
                context.check_hostname = True
            else:
                context.check_hostname = False

            if self._tls_config.verify_mode:
                context.verify_mode = ssl.CERT_REQUIRED
            else:
                context.verify_mode = ssl.CERT_NONE

            if self._tls_config.ca_certs:
                context.load_verify_locations(self._tls_config.ca_certs)

            if self._tls_config.certfile:
                context.load_cert_chain(
                    certfile=self._tls_config.certfile,
                    keyfile=self._tls_config.keyfile,
                )

            return context
        except (ssl.SSLError, OSError, ValueError) as e:
            raise TransportError(f"Failed to create SSL context: {e}") from e

    async def connect(self, remote: tuple[str, int]) -> None:
        """Establish TLS connection to remote address.

        Overrides TcpTransport.connect to use TLS-wrapped connections.

        Raises:
            TransportError: If transport is closed or connection fails.
        """
        if self._closed:
            raise TransportError("Transport is closed")

        if remote in self._connections:
            return

        try:
            reader, writer = await asyncio.open_connection(
                remote[0],
                remote[1],
                ssl=self._ssl_context,
                server_hostname=remote[0] if self._tls_config.check_hostname else None,
            )
            self._connections[remote] = (reader, writer)
            task = asyncio.create_task(self._read_loop(reader, remote))
            self._receive_tasks.add(task)
            task.add_done_callback(self._receive_tasks.discard)
        except ssl.SSLError as e:
            raise TransportError(f"TLS handshake failed with {remote}: {e}") from e
        except OSError as e:
            raise TransportError(f"Failed to connect to {remote}: {e}") from e
