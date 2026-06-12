"""Tests for AsyncClient UAS handler functionality."""

from __future__ import annotations

import pytest

from sipx.client import AsyncClient
from sipx.exceptions import ProtocolError
from sipx.models import Request, Response


def test_asyncclient_has_uas_handlers():
    """AsyncClient must have UAS handler decorator methods."""
    client = AsyncClient()
    assert hasattr(client, "on_invite")
    assert hasattr(client, "on_message")
    assert hasattr(client, "on_options")
    assert hasattr(client, "on_subscribe")


def test_on_invite_registration():
    """on_invite must register an INVITE handler."""
    client = AsyncClient()

    async def handle_invite(request: Request) -> Response:
        return Response(200, "OK", {}, None)

    client.on_invite(handle_invite)
    assert "INVITE" in client._uas_handlers
    assert client._uas_handlers["INVITE"] is handle_invite


def test_on_message_registration():
    """on_message must register a MESSAGE handler."""
    client = AsyncClient()

    async def handle_message(request: Request) -> Response:
        return Response(200, "OK", {}, None)

    client.on_message(handle_message)
    assert "MESSAGE" in client._uas_handlers
    assert client._uas_handlers["MESSAGE"] is handle_message


def test_on_options_registration():
    """on_options must register an OPTIONS handler."""
    client = AsyncClient()

    async def handle_options(request: Request) -> Response:
        return Response(200, "OK", {}, None)

    client.on_options(handle_options)
    assert "OPTIONS" in client._uas_handlers
    assert client._uas_handlers["OPTIONS"] is handle_options


def test_on_subscribe_registration():
    """on_subscribe must register a SUBSCRIBE handler."""
    client = AsyncClient()

    async def handle_subscribe(request: Request) -> Response:
        return Response(200, "OK", {}, None)

    client.on_subscribe(handle_subscribe)
    assert "SUBSCRIBE" in client._uas_handlers
    assert client._uas_handlers["SUBSCRIBE"] is handle_subscribe


@pytest.mark.asyncio
async def test_on_invite_invocation():
    """on_invite handler must be invoked for INVITE requests."""
    client = AsyncClient()
    invoked = []

    async def handle_invite(request: Request) -> Response:
        invoked.append(request)
        return Response(200, "OK", {"Call-ID": "test-call-123", "To": "bob;tag=789", "Contact": "sip:bob@example.com"}, None)

    client.on_invite(handle_invite)

    request = Request(
        method="INVITE",
        uri="sip:bob@example.com",
        headers={"Call-ID": "test-call-123", "From": "alice;tag=456", "To": "bob", "CSeq": "1 INVITE", "Contact": "sip:alice@example.com"},
    )

    response = await client.handle_request(request)
    assert len(invoked) == 1
    assert invoked[0] is request
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_on_message_invocation():
    """on_message handler must be invoked for MESSAGE requests."""
    client = AsyncClient()
    invoked = []

    async def handle_message(request: Request) -> Response:
        invoked.append(request)
        return Response(200, "OK", {}, None)

    client.on_message(handle_message)

    request = Request(
        method="MESSAGE",
        uri="sip:bob@example.com",
        headers={"Call-ID": "test-msg-123"},
    )

    response = await client.handle_request(request)
    assert len(invoked) == 1
    assert invoked[0] is request
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_on_options_invocation():
    """on_options handler must be invoked for OPTIONS requests."""
    client = AsyncClient()
    invoked = []

    async def handle_options(request: Request) -> Response:
        invoked.append(request)
        return Response(200, "OK", {}, None)

    client.on_options(handle_options)

    request = Request(
        method="OPTIONS",
        uri="sip:bob@example.com",
        headers={"Call-ID": "test-opt-123"},
    )

    response = await client.handle_request(request)
    assert len(invoked) == 1
    assert invoked[0] is request
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_on_subscribe_invocation():
    """on_subscribe handler must be invoked for SUBSCRIBE requests."""
    client = AsyncClient()
    invoked = []

    async def handle_subscribe(request: Request) -> Response:
        invoked.append(request)
        return Response(200, "OK", {}, None)

    client.on_subscribe(handle_subscribe)

    request = Request(
        method="SUBSCRIBE",
        uri="sip:bob@example.com",
        headers={"Call-ID": "test-sub-123"},
    )

    response = await client.handle_request(request)
    assert len(invoked) == 1
    assert invoked[0] is request
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_no_handler_raises_protocol_error():
    """handle_request must raise ProtocolError if no handler is registered."""
    client = AsyncClient()

    request = Request(
        method="INVITE",
        uri="sip:bob@example.com",
        headers={},
    )

    with pytest.raises(ProtocolError, match="no handler registered for INVITE"):
        await client.handle_request(request)


@pytest.mark.asyncio
async def test_handler_returns_wrong_type_raises_protocol_error():
    """handle_request must raise ProtocolError if handler returns wrong type."""
    client = AsyncClient()

    async def bad_handler(request: Request) -> str:
        return "not a response"

    client.on_invite(bad_handler)

    request = Request(
        method="INVITE",
        uri="sip:bob@example.com",
        headers={},
    )

    with pytest.raises(ProtocolError, match="must return a Response"):
        await client.handle_request(request)


@pytest.mark.asyncio
async def test_handler_exception_raises_protocol_error():
    """handle_request must raise ProtocolError if handler raises exception."""
    client = AsyncClient()

    async def failing_handler(request: Request) -> Response:
        raise ValueError("handler failed")

    client.on_invite(failing_handler)

    request = Request(
        method="INVITE",
        uri="sip:bob@example.com",
        headers={},
    )

    with pytest.raises(ProtocolError, match="raised an exception"):
        await client.handle_request(request)


@pytest.mark.asyncio
async def test_transaction_management():
    """handle_request must create and manage ServerTransaction."""
    client = AsyncClient()

    async def handle_invite(request: Request) -> Response:
        return Response(200, "OK", {"Call-ID": "test-txn-123", "To": "bob;tag=789", "Contact": "sip:bob@example.com"}, None)

    client.on_invite(handle_invite)

    request = Request(
        method="INVITE",
        uri="sip:bob@example.com",
        headers={"Call-ID": "test-txn-123", "From": "alice;tag=456", "To": "bob", "CSeq": "1 INVITE", "Contact": "sip:alice@example.com"},
    )

    response = await client.handle_request(request)
    assert response.status_code == 200
    assert response.request is request


@pytest.mark.asyncio
async def test_dialog_management():
    """handle_request must create and manage Dialog for INVITE."""
    client = AsyncClient()

    async def handle_invite(request: Request) -> Response:
        return Response(200, "OK", {"Call-ID": "test-dialog-123", "To": "bob;tag=123", "Contact": "sip:bob@example.com"}, None)

    client.on_invite(handle_invite)

    request = Request(
        method="INVITE",
        uri="sip:bob@example.com",
        headers={
            "Call-ID": "test-dialog-123",
            "From": "alice;tag=456",
            "To": "bob",
            "CSeq": "1 INVITE",
            "Contact": "sip:alice@example.com",
        },
    )

    response = await client.handle_request(request)
    assert response.status_code == 200
    assert "test-dialog-123" in client._dialogs
    dialog = client._dialogs["test-dialog-123"]
    assert dialog.state == "Confirmed"


@pytest.mark.asyncio
async def test_multiple_handlers():
    """AsyncClient must support multiple handlers for different methods."""
    client = AsyncClient()
    invite_count = []
    message_count = []

    async def handle_invite(request: Request) -> Response:
        invite_count.append(1)
        return Response(200, "OK", {"Call-ID": "test-multi-1", "To": "bob;tag=789", "Contact": "sip:bob@example.com"}, None)

    async def handle_message(request: Request) -> Response:
        message_count.append(1)
        return Response(200, "OK", {}, None)

    client.on_invite(handle_invite)
    client.on_message(handle_message)

    invite_request = Request(
        method="INVITE",
        uri="sip:bob@example.com",
        headers={"Call-ID": "test-multi-1", "From": "alice;tag=456", "To": "bob", "CSeq": "1 INVITE", "Contact": "sip:alice@example.com"},
    )

    message_request = Request(
        method="MESSAGE",
        uri="sip:bob@example.com",
        headers={"Call-ID": "test-multi-2"},
    )

    await client.handle_request(invite_request)
    await client.handle_request(message_request)

    assert len(invite_count) == 1
    assert len(message_count) == 1


@pytest.mark.asyncio
async def test_handler_decorator_returns_handler():
    """on_* decorators must return the handler for decorator usage."""
    client = AsyncClient()

    @client.on_invite
    async def handle_invite(request: Request) -> Response:
        return Response(200, "OK", {}, None)

    assert handle_invite is not None
    assert "INVITE" in client._uas_handlers
    assert client._uas_handlers["INVITE"] is handle_invite
