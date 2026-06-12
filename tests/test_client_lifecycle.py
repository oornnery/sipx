"""Tests for AsyncClient lifecycle management.

Covers context manager behavior, explicit open/close, receive loop
management, and error handling during the client lifecycle.
"""

from __future__ import annotations

import asyncio

import pytest

from sipx.client import AsyncClient
from sipx.exceptions import TransportError


# ---------------------------------------------------------------------------
# Construction / closed state
# ---------------------------------------------------------------------------

def test_client_starts_closed() -> None:
    """AsyncClient must start in a closed state after construction."""
    client = AsyncClient()
    assert client.is_closed


# ---------------------------------------------------------------------------
# __aenter__
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_aenter_opens_client() -> None:
    """__aenter__ must transition is_closed from True to False."""
    client = AsyncClient()
    assert client.is_closed
    await client.__aenter__()
    assert not client.is_closed
    await client.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_aenter_starts_udp_transport() -> None:
    """__aenter__ must start a UDP transport so local_address works."""
    client = AsyncClient(transport="udp")
    await client.__aenter__()
    try:
        host, port = client.transport.local_address
        assert host in ("0.0.0.0", "127.0.0.1")
        assert port > 0
    finally:
        await client.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_aenter_starts_receive_loop() -> None:
    """__aenter__ must create a background receive loop task."""
    client = AsyncClient()
    await client.__aenter__()
    try:
        assert client._receive_task is not None
        assert not client._receive_task.done()
    finally:
        await client.__aexit__(None, None, None)


# ---------------------------------------------------------------------------
# __aexit__
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_aexit_closes_client() -> None:
    """__aexit__ must transition is_closed back to True."""
    client = AsyncClient()
    await client.__aenter__()
    assert not client.is_closed
    await client.__aexit__(None, None, None)
    assert client.is_closed


@pytest.mark.asyncio
async def test_aexit_cancels_receive_loop() -> None:
    """__aexit__ must cancel the background receive loop task."""
    client = AsyncClient()
    await client.__aenter__()
    assert client._receive_task is not None
    await client.__aexit__(None, None, None)
    assert client._receive_task is None or client._receive_task.done()


@pytest.mark.asyncio
async def test_aexit_closes_transport() -> None:
    """__aexit__ must close the underlying transport."""
    client = AsyncClient(transport="udp")
    await client.__aenter__()
    await client.__aexit__(None, None, None)
    # After close, UDP transport local_address must raise
    with pytest.raises(TransportError):
        client.transport.local_address


# ---------------------------------------------------------------------------
# Context manager (combined enter + exit)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_context_manager_basic() -> None:
    """async with must open the client on entry and close on exit."""
    async with AsyncClient() as client:
        assert not client.is_closed
        assert client._receive_task is not None
    assert client.is_closed


@pytest.mark.asyncio
async def test_context_manager_with_exception() -> None:
    """async with must close the client even when the body raises."""
    client = AsyncClient()
    with pytest.raises(ValueError, match="boom"):
        async with client:
            assert not client.is_closed
            raise ValueError("boom")
    assert client.is_closed


# ---------------------------------------------------------------------------
# aclose()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_aclose_closes_opened_client() -> None:
    """aclose() must close a client that was opened via __aenter__."""
    client = AsyncClient()
    await client.__aenter__()
    assert not client.is_closed
    await client.aclose()
    assert client.is_closed


@pytest.mark.asyncio
async def test_aclose_idempotent() -> None:
    """aclose() must be safe to call multiple times."""
    client = AsyncClient()
    await client.__aenter__()
    await client.aclose()
    await client.aclose()  # must not raise
    assert client.is_closed


@pytest.mark.asyncio
async def test_aclose_without_enter_is_safe() -> None:
    """aclose() on a never-entered client must be a no-op."""
    client = AsyncClient()
    assert client.is_closed
    await client.aclose()  # must not raise
    assert client.is_closed
