"""Tests for RFC 3856/3858 Presence Event Package in sipx.rfc.presence."""

from __future__ import annotations

import pytest

from sipx.exceptions import ProtocolError
from sipx.models import Request, Response
from sipx.rfc.events import SubscriptionDialog, SubscriptionState
from sipx.rfc.presence import (
    PIDF_NS,
    PRESENCE_EVENT_PACKAGE,
    PresenceEventPackage,
    PresenceTuple,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SIMPLE_PIDF = """\
<?xml version="1.0" encoding="UTF-8"?>
<presence xmlns="urn:ietf:params:xml:ns:pidf" entity="pres:bob@example.com">
  <tuple id="t1">
    <status><basic>open</basic></status>
    <contact>sip:bob@example.com</contact>
  </tuple>
</presence>"""

MULTI_TUPLE_PIDF = """\
<?xml version="1.0" encoding="UTF-8"?>
<presence xmlns="urn:ietf:params:xml:ns:pidf" entity="pres:alice@example.com">
  <tuple id="work">
    <status><basic>open</basic></status>
    <contact>sip:alice@work.example.com</contact>
    <note>At work</note>
  </tuple>
  <tuple id="mobile">
    <status><basic>closed</basic></status>
    <contact>sip:alice@mobile.example.com</contact>
  </tuple>
</presence>"""


def _subscribe_request(
    event: str = "presence",
    expires: str = "3600",
) -> Request:
    """Build a minimal SUBSCRIBE request."""
    return Request(
        method="SUBSCRIBE",
        uri="sip:bob@example.com",
        headers={
            "Event": event,
            "Expires": expires,
            "From": "sip:alice@example.com",
            "To": "sip:bob@example.com",
        },
    )


def _notify_request(body: bytes | None = None) -> Request:
    """Build a minimal NOTIFY request with PIDF body."""
    return Request(
        method="NOTIFY",
        uri="sip:alice@example.com",
        headers={
            "Event": "presence",
            "Content-Type": "application/pidf+xml",
            "Subscription-State": "active",
        },
        body=body,
    )


# ===========================================================================
# Import and Instantiation
# ===========================================================================


class TestPresenceImport:
    """Basic import and instantiation tests."""

    def test_import_presence_event_package(self):
        """PresenceEventPackage can be imported."""
        from sipx.rfc.presence import PresenceEventPackage as PEP

        assert PEP is not None

    def test_import_presence_tuple(self):
        """PresenceTuple can be imported."""
        from sipx.rfc.presence import PresenceTuple as PT

        assert PT is not None

    def test_create_presence_event_package(self):
        """PresenceEventPackage can be created with entity and tuples."""
        pkg = PresenceEventPackage(
            entity="pres:bob@example.com",
            tuples=[PresenceTuple(id="t1", status="open", contact="sip:bob@example.com")],
        )
        assert pkg.entity == "pres:bob@example.com"
        assert len(pkg.tuples) == 1


# ===========================================================================
# PIDF XML Parsing
# ===========================================================================


class TestPidfParsing:
    """Tests for PIDF XML parsing."""

    def test_parse_simple_pidf(self):
        """from_pidf parses a simple PIDF document."""
        presence = PresenceEventPackage.from_pidf(SIMPLE_PIDF)
        assert presence.entity == "pres:bob@example.com"
        assert len(presence.tuples) == 1

    def test_parse_tuple_status(self):
        """Parsed tuple has correct status."""
        presence = PresenceEventPackage.from_pidf(SIMPLE_PIDF)
        assert presence.tuples[0].status == "open"

    def test_parse_tuple_contact(self):
        """Parsed tuple has correct contact."""
        presence = PresenceEventPackage.from_pidf(SIMPLE_PIDF)
        assert presence.tuples[0].contact == "sip:bob@example.com"

    def test_parse_multi_tuple(self):
        """from_pidf parses multiple tuples."""
        presence = PresenceEventPackage.from_pidf(MULTI_TUPLE_PIDF)
        assert len(presence.tuples) == 2
        assert presence.tuples[0].id == "work"
        assert presence.tuples[1].id == "mobile"

    def test_parse_tuple_note(self):
        """Parsed tuple includes note text."""
        presence = PresenceEventPackage.from_pidf(MULTI_TUPLE_PIDF)
        assert presence.tuples[0].note == "At work"

    def test_parse_malformed_xml_raises_error(self):
        """Malformed XML raises ProtocolError."""
        with pytest.raises(ProtocolError, match="[Mm]alformed"):
            PresenceEventPackage.from_pidf("<not valid xml")

    def test_parse_wrong_namespace_raises_error(self):
        """Wrong XML namespace raises ProtocolError."""
        bad_xml = '<presence xmlns="http://wrong.ns" entity="pres:x"/>'
        with pytest.raises(ProtocolError, match="namespace|root"):
            PresenceEventPackage.from_pidf(bad_xml)

    def test_parse_missing_entity_raises_error(self):
        """Missing entity attribute raises ProtocolError."""
        bad_xml = (
            '<?xml version="1.0"?>'
            '<presence xmlns="urn:ietf:params:xml:ns:pidf">'
            '<tuple id="t1"><status><basic>open</basic></status></tuple>'
            "</presence>"
        )
        with pytest.raises(ProtocolError, match="entity"):
            PresenceEventPackage.from_pidf(bad_xml)


# ===========================================================================
# PIDF XML Generation
# ===========================================================================


class TestPidfGeneration:
    """Tests for PIDF XML generation."""

    def test_generate_pidf_contains_namespace(self):
        """Generated PIDF contains the PIDF namespace."""
        pkg = PresenceEventPackage(
            entity="pres:bob@example.com",
            tuples=[PresenceTuple(id="t1", status="open", contact="sip:bob@example.com")],
        )
        pidf = pkg.to_pidf()
        assert PIDF_NS in pidf

    def test_generate_pidf_contains_entity(self):
        """Generated PIDF contains the entity URI."""
        pkg = PresenceEventPackage(
            entity="pres:bob@example.com",
            tuples=[PresenceTuple(id="t1", status="open")],
        )
        pidf = pkg.to_pidf()
        assert "pres:bob@example.com" in pidf

    def test_generate_pidf_contains_basic_status(self):
        """Generated PIDF contains basic status element."""
        pkg = PresenceEventPackage(
            entity="pres:bob@example.com",
            tuples=[PresenceTuple(id="t1", status="open", contact="sip:bob@example.com")],
        )
        pidf = pkg.to_pidf()
        assert "<basic>open</basic>" in pidf

    def test_roundtrip_pidf(self):
        """PIDF can be generated and re-parsed without data loss."""
        original = PresenceEventPackage(
            entity="pres:alice@example.com",
            tuples=[
                PresenceTuple(id="t1", status="open", contact="sip:alice@example.com"),
                PresenceTuple(id="t2", status="closed", contact="sip:alice@home.example.com"),
            ],
        )
        pidf_xml = original.to_pidf()
        parsed = PresenceEventPackage.from_pidf(pidf_xml)

        assert parsed.entity == original.entity
        assert len(parsed.tuples) == len(original.tuples)
        assert parsed.tuples[0].id == "t1"
        assert parsed.tuples[0].status == "open"
        assert parsed.tuples[1].id == "t2"
        assert parsed.tuples[1].status == "closed"


# ===========================================================================
# Presence State Tracking
# ===========================================================================


class TestPresenceState:
    """Tests for presence state derivation."""

    def test_open_tuple_is_online(self):
        """An open tuple without note derives 'online' state."""
        tup = PresenceTuple(id="t1", status="open", contact="sip:bob@example.com")
        assert tup.presence_state == "online"

    def test_closed_tuple_is_offline(self):
        """A closed tuple derives 'offline' state."""
        tup = PresenceTuple(id="t1", status="closed")
        assert tup.presence_state == "offline"

    def test_busy_note_derives_busy(self):
        """A tuple with 'busy' in note derives 'busy' state."""
        tup = PresenceTuple(id="t1", status="open", note="Busy in meeting")
        assert tup.presence_state == "busy"

    def test_away_note_derives_away(self):
        """A tuple with 'away' in note derives 'away' state."""
        tup = PresenceTuple(id="t1", status="open", note="Away from desk")
        assert tup.presence_state == "away"

    def test_overall_state_online(self):
        """Overall state is 'online' when at least one tuple is open."""
        pkg = PresenceEventPackage(
            entity="pres:bob@example.com",
            tuples=[
                PresenceTuple(id="t1", status="open", contact="sip:bob@example.com"),
                PresenceTuple(id="t2", status="closed"),
            ],
        )
        assert pkg.overall_state == "online"

    def test_overall_state_offline(self):
        """Overall state is 'offline' when all tuples are closed."""
        pkg = PresenceEventPackage(
            entity="pres:bob@example.com",
            tuples=[
                PresenceTuple(id="t1", status="closed"),
                PresenceTuple(id="t2", status="closed"),
            ],
        )
        assert pkg.overall_state == "offline"

    def test_overall_state_unknown_no_tuples(self):
        """Overall state is 'unknown' when no tuples exist."""
        pkg = PresenceEventPackage(entity="pres:bob@example.com")
        assert pkg.overall_state == "unknown"

    def test_find_tuple_by_id(self):
        """find_tuple returns the matching tuple."""
        pkg = PresenceEventPackage(
            entity="pres:bob@example.com",
            tuples=[
                PresenceTuple(id="t1", status="open"),
                PresenceTuple(id="t2", status="closed"),
            ],
        )
        found = pkg.find_tuple("t2")
        assert found is not None
        assert found.id == "t2"
        assert found.status == "closed"

    def test_find_tuple_not_found(self):
        """find_tuple returns None for unknown ID."""
        pkg = PresenceEventPackage(
            entity="pres:bob@example.com",
            tuples=[PresenceTuple(id="t1", status="open")],
        )
        assert pkg.find_tuple("nonexistent") is None


# ===========================================================================
# SubscriptionDialog Integration
# ===========================================================================


class TestSubscriptionIntegration:
    """Tests for integration with SubscriptionDialog."""

    def test_create_subscription(self):
        """create_subscription returns a SubscriptionDialog for presence."""
        dialog = PresenceEventPackage.create_subscription(
            subscriber_uri="sip:alice@example.com",
            notifier_uri="sip:bob@example.com",
            call_id="call-123",
        )
        assert isinstance(dialog, SubscriptionDialog)
        assert dialog.event == PRESENCE_EVENT_PACKAGE

    def test_build_notify_request(self):
        """build_notify_request creates a NOTIFY with PIDF body."""
        pkg = PresenceEventPackage(
            entity="pres:bob@example.com",
            tuples=[PresenceTuple(id="t1", status="open", contact="sip:bob@example.com")],
        )
        dialog = PresenceEventPackage.create_subscription(
            subscriber_uri="sip:alice@example.com",
            notifier_uri="sip:bob@example.com",
            call_id="call-123",
        )
        dialog._subscription_state = SubscriptionState.ACTIVE

        notify = pkg.build_notify_request(dialog)
        assert isinstance(notify, Request)
        assert notify.method == "NOTIFY"
        assert notify.body is not None
        assert b"pres:bob@example.com" in notify.body

    def test_parse_notify_request(self):
        """parse_notify extracts presence from a NOTIFY request."""
        pidf_body = SIMPLE_PIDF.encode("utf-8")
        request = _notify_request(body=pidf_body)

        presence = PresenceEventPackage.parse_notify(request)
        assert presence.entity == "pres:bob@example.com"
        assert len(presence.tuples) == 1

    def test_parse_notify_no_body_raises_error(self):
        """parse_notify raises ProtocolError for empty body."""
        request = _notify_request(body=None)
        with pytest.raises(ProtocolError, match="no body"):
            PresenceEventPackage.parse_notify(request)


# ===========================================================================
# SUBSCRIBE Validation
# ===========================================================================


class TestSubscribeValidation:
    """Tests for SUBSCRIBE request validation."""

    def test_validate_subscribe_presence(self):
        """validate_subscribe accepts a valid presence SUBSCRIBE."""
        request = _subscribe_request(event="presence")
        PresenceEventPackage.validate_subscribe(request)  # Should not raise

    def test_validate_subscribe_missing_event(self):
        """validate_subscribe rejects SUBSCRIBE without Event header."""
        request = Request(
            method="SUBSCRIBE",
            uri="sip:bob@example.com",
            headers={"Expires": "3600"},
        )
        with pytest.raises(ProtocolError, match="Event"):
            PresenceEventPackage.validate_subscribe(request)

    def test_validate_subscribe_wrong_event(self):
        """validate_subscribe rejects SUBSCRIBE with wrong event package."""
        request = _subscribe_request(event="message-summary")
        with pytest.raises(ProtocolError, match="presence"):
            PresenceEventPackage.validate_subscribe(request)


# ===========================================================================
# PresenceTuple Validation
# ===========================================================================


class TestPresenceTupleValidation:
    """Tests for PresenceTuple validation."""

    def test_invalid_status_raises_error(self):
        """PresenceTuple with invalid status raises ProtocolError."""
        with pytest.raises(ProtocolError, match="status"):
            PresenceTuple(id="t1", status="invalid")

    def test_is_open_true(self):
        """is_open returns True for open tuple."""
        tup = PresenceTuple(id="t1", status="open")
        assert tup.is_open is True

    def test_is_open_false(self):
        """is_open returns False for closed tuple."""
        tup = PresenceTuple(id="t1", status="closed")
        assert tup.is_open is False
