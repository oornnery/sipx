"""Tests for provisional response streaming in sipx.protocol.provisional."""

from __future__ import annotations

import asyncio

import pytest

from sipx.exceptions import ProtocolError
from sipx.models import Request, Response
from sipx.protocol.provisional import ProvisionalStream
from sipx.protocol.transaction import ClientTransaction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _invite_request() -> Request:
    return Request(method="INVITE", uri="sip:bob@example.com", headers={}, body=None)


def _response(status_code: int, reason: str = "") -> Response:
    reasons = {
        100: "Trying",
        180: "Ringing",
        183: "Session Progress",
        200: "OK",
        404: "Not Found",
        487: "Request Terminated",
    }
    return Response(
        status_code=status_code,
        reason=reason or reasons.get(status_code, "Unknown"),
        headers={},
        body=None,
    )


async def _feed_sequence(stream: ProvisionalStream, responses: list[Response]) -> None:
    """Feed a sequence of responses into the stream with small delays."""
    for resp in responses:
        await stream.feed(resp)
        await asyncio.sleep(0)


async def _collect(stream: ProvisionalStream, max_items: int = 20) -> list[Response]:
    """Collect responses from the stream until it closes or max_items reached."""
    collected: list[Response] = []
    async for resp in stream:
        collected.append(resp)
        if len(collected) >= max_items:
            break
    return collected


# ===========================================================================
# ProvisionalStream — Basic Streaming
# ===========================================================================


class TestProvisionalStreamBasic:
    """Basic provisional response streaming tests."""

    @pytest.mark.asyncio
    async def test_stream_yields_provisional_responses_in_order(self):
        """Stream yields provisional responses in the order they arrive."""
        stream = ProvisionalStream()
        responses = [_response(100), _response(180), _response(200)]

        asyncio.create_task(_feed_sequence(stream, responses))

        collected = await _collect(stream)
        assert [r.status_code for r in collected] == [100, 180, 200]

    @pytest.mark.asyncio
    async def test_stream_yields_final_response_only(self):
        """Stream yields a final response when no provisionals precede it."""
        stream = ProvisionalStream()
        asyncio.create_task(_feed_sequence(stream, [_response(200)]))

        collected = await _collect(stream)
        assert [r.status_code for r in collected] == [200]

    @pytest.mark.asyncio
    async def test_stream_auto_closes_on_final_response(self):
        """Stream closes automatically after yielding a final response."""
        stream = ProvisionalStream()
        asyncio.create_task(_feed_sequence(stream, [_response(100), _response(200)]))

        collected = await _collect(stream)
        assert [r.status_code for r in collected] == [100, 200]
        assert stream.closed


# ===========================================================================
# ProvisionalStream — Filtering
# ===========================================================================


class TestProvisionalStreamFiltering:
    """Status-code filtering tests."""

    @pytest.mark.asyncio
    async def test_stream_filters_by_single_status_code(self):
        """Stream filters provisionals by a single status code."""
        stream = ProvisionalStream(status_codes=[180])
        responses = [_response(100), _response(180), _response(200)]

        asyncio.create_task(_feed_sequence(stream, responses))

        collected = await _collect(stream)
        assert [r.status_code for r in collected] == [180, 200]

    @pytest.mark.asyncio
    async def test_stream_filters_by_multiple_status_codes(self):
        """Stream filters provisionals by multiple status codes."""
        stream = ProvisionalStream(status_codes=[100, 183])
        responses = [
            _response(100),
            _response(180),
            _response(183),
            _response(200),
        ]

        asyncio.create_task(_feed_sequence(stream, responses))

        collected = await _collect(stream)
        assert [r.status_code for r in collected] == [100, 183, 200]

    @pytest.mark.asyncio
    async def test_stream_filter_allows_all_final_responses(self):
        """Final responses always pass through regardless of filter."""
        stream = ProvisionalStream(status_codes=[180])
        responses = [_response(100), _response(404)]

        asyncio.create_task(_feed_sequence(stream, responses))

        collected = await _collect(stream)
        assert [r.status_code for r in collected] == [404]


# ===========================================================================
# ProvisionalStream — Timeout
# ===========================================================================


class TestProvisionalStreamTimeout:
    """Timeout behavior tests."""

    @pytest.mark.asyncio
    async def test_stream_timeout_raises_protocol_error(self):
        """Stream raises ProtocolError when timeout expires with no response."""
        stream = ProvisionalStream(timeout=0.01)

        with pytest.raises(ProtocolError, match="timed out"):
            await stream.__anext__()

        assert stream.closed

    @pytest.mark.asyncio
    async def test_stream_timeout_after_provisional(self):
        """Stream yields provisional then raises ProtocolError on timeout."""
        stream = ProvisionalStream(timeout=0.05)

        await stream.feed(_response(100))

        first = await stream.__anext__()
        assert first.status_code == 100

        with pytest.raises(ProtocolError, match="timed out"):
            await stream.__anext__()


# ===========================================================================
# ProvisionalStream — Close and Error Handling
# ===========================================================================


class TestProvisionalStreamClose:
    """Close and error handling tests."""

    @pytest.mark.asyncio
    async def test_stream_close_stops_iteration(self):
        """Closing the stream causes __anext__ to raise StopAsyncIteration."""
        stream = ProvisionalStream()
        await stream.feed(_response(100))

        first = await stream.__anext__()
        assert first.status_code == 100

        stream.close()

        with pytest.raises(StopAsyncIteration):
            await stream.__anext__()

    @pytest.mark.asyncio
    async def test_stream_feed_after_close_raises_protocol_error(self):
        """Feeding a response into a closed stream raises ProtocolError."""
        stream = ProvisionalStream()
        stream.close()

        with pytest.raises(ProtocolError, match="closed"):
            await stream.feed(_response(100))


# ===========================================================================
# ProvisionalStream — Transaction Integration
# ===========================================================================


class TestProvisionalStreamTransaction:
    """Integration with ClientTransaction tests."""

    @pytest.mark.asyncio
    async def test_stream_forwards_responses_to_transaction(self):
        """Stream forwards fed responses to the attached ClientTransaction."""
        txn = ClientTransaction(_invite_request())
        stream = ProvisionalStream(transaction=txn)

        assert txn.state == "Calling"

        await stream.feed(_response(100))
        assert txn.state == "Proceeding"

        await stream.feed(_response(200))
        assert txn.state == "Terminated"

    @pytest.mark.asyncio
    async def test_stream_transaction_property(self):
        """Stream exposes the attached transaction via property."""
        txn = ClientTransaction(_invite_request())
        stream = ProvisionalStream(transaction=txn)
        assert stream.transaction is txn

        stream_no_txn = ProvisionalStream()
        assert stream_no_txn.transaction is None
