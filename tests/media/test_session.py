"""Tests for DTMFHelper and CallSession."""

from __future__ import annotations

from unittest.mock import MagicMock

from sipx.media._session import CallSession, DTMFHelper


class TestDTMFHelper:
    def test_created_with_mock_rtp(self):
        rtp = MagicMock()
        helper = DTMFHelper(rtp)
        assert helper._rtp is rtp

    def test_sender_lazy_init(self):
        rtp = MagicMock()
        helper = DTMFHelper(rtp)
        assert helper._sender is None


class TestCallSession:
    def test_rtp_none_without_sdp(self):
        client = MagicMock()
        response = MagicMock()
        response.body = None
        session = CallSession(client, response, rtp_port=8000)
        assert session.rtp is None

    def test_dtmf_none_without_rtp(self):
        client = MagicMock()
        response = MagicMock()
        response.body = None
        session = CallSession(client, response, rtp_port=8000)
        assert session.dtmf is None

    def test_properties_with_sdp(self):
        client = MagicMock()
        client.local_address.host = "127.0.0.1"
        response = MagicMock()
        body = MagicMock()
        body.get_rtp_params = MagicMock()
        body.get_connection_address.return_value = "127.0.0.1"
        body.get_media_ports.return_value = {"audio": 49170}
        body.get_accepted_codecs.return_value = [
            {"payload": "0", "name": "PCMU", "rate": "8000"}
        ]
        response.body = body
        session = CallSession(client, response, rtp_port=8000)
        assert session.rtp is not None
        assert session.dtmf is not None
