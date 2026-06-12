"""Provisional response streaming for SIP client transactions.

Provides an async iterator that yields provisional (1xx) SIP responses
as they arrive, with optional status-code filtering and timeout support.
Integrates with ClientTransaction without modifying its state machine.

RFC 3261 §17.1.1 — INVITE client transaction provisional responses.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import TYPE_CHECKING

from sipx.exceptions import ProtocolError
from sipx.models import Response

if TYPE_CHECKING:
    from sipx.protocol.transaction import ClientTransaction


class ProvisionalStream:
    """Async iterator that yields provisional (1xx) SIP responses as they arrive.

    Supports filtering by status code and timeout. Optionally forwards
    responses to a ``ClientTransaction`` for state-machine tracking.

    Usage::

        stream = ProvisionalStream(status_codes=[180], timeout=30.0)
        async for response in stream:
            print(response.status_code, response.reason)
            if response.status_code >= 200:
                break

    Responses with status codes in the 1xx range are provisional.
    Final responses (>= 200) always pass through and close the stream.
    """

    def __init__(
        self,
        *,
        status_codes: Iterable[int] | None = None,
        timeout: float | None = None,
        transaction: ClientTransaction | None = None,
    ) -> None:
        """Initialize a provisional response stream.

        Args:
            status_codes: If provided, only yield provisional responses whose
                status code is in this set. Final responses (>= 200) always
                pass through regardless of this filter.
            timeout: Maximum seconds to wait for the next response. If the
                timeout expires, a ``ProtocolError`` is raised.
            transaction: Optional ``ClientTransaction`` to forward responses
                to. When set, each fed response is also processed by the
                transaction's state machine.
        """
        self._status_codes: set[int] | None = (
            set(status_codes) if status_codes is not None else None
        )
        self._timeout = timeout
        self._transaction = transaction
        self._queue: asyncio.Queue[Response] = asyncio.Queue()
        self._closed = False

    @property
    def closed(self) -> bool:
        """Whether the stream has been closed."""
        return self._closed

    @property
    def transaction(self) -> ClientTransaction | None:
        """The associated client transaction, if any."""
        return self._transaction

    async def feed(self, response: Response) -> None:
        """Feed a response into the stream.

        If a ``ClientTransaction`` is attached, the response is forwarded
        to it before being queued for iteration.

        Args:
            response: The SIP response to feed into the stream.

        Raises:
            ProtocolError: If the stream is already closed.
        """
        if self._closed:
            raise ProtocolError(
                "Cannot feed response into a closed provisional stream",
                rfc_ref="RFC 3261 §17.1.1",
            )
        if self._transaction is not None:
            self._transaction.receive_response(
                response.status_code,
                response.reason,
                dict(response.headers),
                response.body,
            )
        await self._queue.put(response)

    def close(self) -> None:
        """Close the stream, stopping further iteration.

        After closing, ``__anext__`` raises ``StopAsyncIteration`` and
        ``feed`` raises ``ProtocolError``.
        """
        self._closed = True

    def __aiter__(self) -> ProvisionalStream:
        return self

    async def __anext__(self) -> Response:
        while True:
            if self._closed:
                raise StopAsyncIteration

            try:
                if self._timeout is not None:
                    response = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=self._timeout,
                    )
                else:
                    response = await self._queue.get()
            except asyncio.TimeoutError:
                self._closed = True
                raise ProtocolError(
                    f"Provisional stream timed out after {self._timeout}s",
                    rfc_ref="RFC 3261 §17.1.1",
                )

            # Filter provisional responses by status code.
            if 100 <= response.status_code < 200:
                if (
                    self._status_codes is not None
                    and response.status_code not in self._status_codes
                ):
                    continue

            # Final response closes the stream after yielding.
            if response.status_code >= 200:
                self._closed = True

            return response
