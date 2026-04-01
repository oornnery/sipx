"""Tests for RFC 3863 PIFDBody and RFC 3903 PUBLISH presence."""

from __future__ import annotations

from unittest.mock import patch

from sipx.client import Client
from sipx.models import PIFDBody
from sipx.models._message import Response
from sipx._types import TransportAddress
from sipx.transports._base import BaseTransport


# ============================================================================
# Helpers
# ============================================================================


class MockTransport(BaseTransport):
    def __init__(self, config=None):
        super().__init__(config)
        self.sent: list[tuple[bytes, TransportAddress]] = []
        self._queue: list[bytes] = []

    def send(self, data, destination):
        self.sent.append((data, destination))

    def receive(self, timeout=None):
        if not self._queue:
            raise TimeoutError("No queued responses")
        return self._queue.pop(0), TransportAddress(host="127.0.0.1", port=5060)

    def handle_request(self, request, destination):
        raise NotImplementedError

    def close(self):
        self._closed = True

    def _get_protocol_name(self):
        return "UDP"


def _make_response(status: int, reason: str, extra: dict | None = None) -> bytes:
    headers = {
        "Via": "SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bKtest",
        "From": "<sip:alice@127.0.0.1>;tag=abc",
        "To": "<sip:alice@127.0.0.1>",
        "Call-ID": "pub@127.0.0.1",
        "CSeq": "1 PUBLISH",
        "Content-Length": "0",
    }
    if extra:
        headers.update(extra)
    return Response(status_code=status, reason_phrase=reason, headers=headers).to_bytes()


# ============================================================================
# PIFDBody
# ============================================================================


class TestPIFDBody:
    def test_to_string_contains_entity(self):
        pidf = PIFDBody(entity="sip:alice@pbx.com")
        xml = pidf.to_string()
        assert 'entity="sip:alice@pbx.com"' in xml

    def test_to_string_open_status(self):
        pidf = PIFDBody(entity="sip:alice@pbx.com", status="open")
        assert "<basic>open</basic>" in pidf.to_string()

    def test_to_string_closed_status(self):
        pidf = PIFDBody(entity="sip:alice@pbx.com", status="closed")
        assert "<basic>closed</basic>" in pidf.to_string()

    def test_to_string_with_note(self):
        pidf = PIFDBody(entity="sip:alice@pbx.com", note="At desk")
        assert "<note>At desk</note>" in pidf.to_string()

    def test_to_string_no_note(self):
        pidf = PIFDBody(entity="sip:alice@pbx.com")
        assert "<note>" not in pidf.to_string()

    def test_content_type(self):
        pidf = PIFDBody(entity="sip:alice@pbx.com")
        assert pidf.content_type == "application/pidf+xml"

    def test_to_bytes_is_utf8(self):
        pidf = PIFDBody(entity="sip:alice@pbx.com")
        b = pidf.to_bytes()
        assert isinstance(b, bytes)
        assert b"application/pidf" not in b  # body doesn't contain content-type
        assert b"<presence" in b

    def test_valid_xml_structure(self):
        pidf = PIFDBody(entity="sip:alice@pbx.com", status="open")
        xml = pidf.to_string()
        assert xml.startswith("<?xml")
        assert "<presence" in xml
        assert "<tuple" in xml
        assert "</presence>" in xml


class TestPIFDBodyParse:
    def _make_xml(self, entity: str, status: str, note: str = "") -> str:
        note_xml = f"<note>{note}</note>" if note else ""
        return (
            '<?xml version="1.0"?>'
            f'<presence xmlns="urn:ietf:params:xml:ns:pidf" entity="{entity}">'
            f'<tuple id="t1"><status><basic>{status}</basic></status>'
            f"{note_xml}</tuple></presence>"
        )

    def test_parse_entity(self):
        xml = self._make_xml("sip:bob@example.com", "open")
        pidf = PIFDBody.parse(xml)
        assert pidf.entity == "sip:bob@example.com"

    def test_parse_open_status(self):
        xml = self._make_xml("sip:bob@example.com", "open")
        pidf = PIFDBody.parse(xml)
        assert pidf.status == "open"

    def test_parse_closed_status(self):
        xml = self._make_xml("sip:bob@example.com", "closed")
        pidf = PIFDBody.parse(xml)
        assert pidf.status == "closed"

    def test_parse_note(self):
        xml = self._make_xml("sip:bob@example.com", "open", note="In a meeting")
        pidf = PIFDBody.parse(xml)
        assert pidf.note == "In a meeting"

    def test_parse_bytes(self):
        xml = self._make_xml("sip:bob@example.com", "open")
        pidf = PIFDBody.parse(xml.encode())
        assert pidf.entity == "sip:bob@example.com"

    def test_roundtrip(self):
        original = PIFDBody(entity="sip:alice@pbx.com", status="open", note="Hi")
        parsed = PIFDBody.parse(original.to_string())
        assert parsed.entity == original.entity
        assert parsed.status == original.status
        assert parsed.note == original.note


# ============================================================================
# Client.publish() — RFC 3903
# ============================================================================


class TestPublish:
    @patch("sipx.client._sync._create_sync_transport")
    def test_publish_sends_event_header(self, mock_create):
        transport = MockTransport()
        mock_create.return_value = transport
        transport._queue.append(_make_response(200, "OK", {"SIP-ETag": "etag1"}))

        client = Client()
        pidf = PIFDBody(entity="sip:alice@127.0.0.1", status="open")
        client.publish("sip:alice@127.0.0.1", content=pidf.to_string())

        sent = transport.sent[0][0].decode()
        assert "Event: presence" in sent

    @patch("sipx.client._sync._create_sync_transport")
    def test_publish_stores_sip_etag(self, mock_create):
        transport = MockTransport()
        mock_create.return_value = transport
        transport._queue.append(_make_response(200, "OK", {"SIP-ETag": "abc123"}))

        client = Client()
        client.publish("sip:alice@127.0.0.1", content="<presence/>")

        assert client._presence_etag == "abc123"

    @patch("sipx.client._sync._create_sync_transport")
    def test_publish_refresh_sends_sip_if_match(self, mock_create):
        transport = MockTransport()
        mock_create.return_value = transport
        transport._queue.append(_make_response(200, "OK", {"SIP-ETag": "etag2"}))

        client = Client()
        client._presence_etag = "etag1"
        client.publish("sip:alice@127.0.0.1", etag="etag1")

        sent = transport.sent[0][0].decode()
        assert "SIP-If-Match: etag1" in sent

    @patch("sipx.client._sync._create_sync_transport")
    def test_publish_no_etag_on_non_200(self, mock_create):
        transport = MockTransport()
        mock_create.return_value = transport
        transport._queue.append(_make_response(412, "Conditional Request Failed"))

        client = Client()
        client.publish("sip:alice@127.0.0.1", etag="stale")

        assert client._presence_etag is None

    @patch("sipx.client._sync._create_sync_transport")
    def test_publish_content_type_pidf_xml(self, mock_create):
        transport = MockTransport()
        mock_create.return_value = transport
        transport._queue.append(_make_response(200, "OK"))

        client = Client()
        pidf = PIFDBody(entity="sip:alice@127.0.0.1")
        client.publish("sip:alice@127.0.0.1", content=pidf.to_string())

        sent = transport.sent[0][0].decode()
        assert "application/pidf+xml" in sent
