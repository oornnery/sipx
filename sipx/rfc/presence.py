"""RFC 3856 / RFC 3858 Presence Event Package with PIDF.

This module implements the presence event package for SIP (RFC 3856)
using the Presence Information Data Format (PIDF, RFC 3858). It provides
parsing and generation of PIDF XML, presence state tracking, and
integration with the SIP SUBSCRIBE/NOTIFY framework from RFC 3265.

References:
    RFC 3856 - A Presence Event Package for the Session Initiation
               Protocol (SIP)
    RFC 3858 - An Extensible Markup Language (XML) Based Format for
               Presence Information (PIDF)
    RFC 3265 - SIP-Specific Event Notification
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sipx.exceptions import ProtocolError
from sipx.models import Request
from sipx.rfc.events import SubscriptionDialog, SubscriptionState

if TYPE_CHECKING:
    pass

#: PIDF XML namespace per RFC 3858 §2.
PIDF_NS = "urn:ietf:params:xml:ns:pidf"

#: Presence event package name per RFC 3856 §3.
PRESENCE_EVENT_PACKAGE = "presence"

#: Valid PIDF basic status values per RFC 3858 §2.2.2.
VALID_BASIC_STATUSES = frozenset({"open", "closed"})

#: Common presence state labels derived from basic status and notes.
PRESENCE_STATES = frozenset(
    {
        "online",
        "offline",
        "busy",
        "away",
        "on-the-phone",
        "unknown",
    }
)


@dataclass
class PresenceTuple:
    """A single PIDF tuple element representing one contact point.

    Per RFC 3858 §2.2, a tuple contains status and contact information
    for one aspect of a presentity.

    Attributes:
        id: Unique tuple identifier within the PIDF document.
        status: Basic status value ('open' or 'closed').
        contact: SIP URI or other contact address.
        note: Optional human-readable status note.
    """

    id: str
    status: str = "closed"
    contact: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        """Validate the tuple status after initialization.

        Raises:
            ProtocolError: If status is not 'open' or 'closed'.
        """
        if self.status not in VALID_BASIC_STATUSES:
            raise ProtocolError(
                f"Invalid PIDF basic status: {self.status!r} "
                f"(must be 'open' or 'closed')",
                rfc_ref="RFC 3858 §2.2.2",
            )

    @property
    def is_open(self) -> bool:
        """Return True if the tuple status is 'open'."""
        return self.status == "open"

    @property
    def presence_state(self) -> str:
        """Derive a high-level presence state from tuple data.

        Returns one of: 'online', 'offline', 'busy', 'away',
        'on-the-phone', or 'unknown'.
        """
        if self.status == "closed":
            return "offline"
        # Status is 'open' — refine using note if available
        if self.note:
            note_lower = self.note.lower()
            if "busy" in note_lower:
                return "busy"
            if "away" in note_lower:
                return "away"
            if "phone" in note_lower or "call" in note_lower:
                return "on-the-phone"
        return "online"


@dataclass
class PresenceEventPackage:
    """Presence event package implementing RFC 3856 and RFC 3858.

    Manages presence information for a presentity (presence entity),
    including PIDF XML parsing/generation and integration with the
    SIP SUBSCRIBE/NOTIFY framework.

    Attributes:
        entity: The presentity URI (e.g., 'pres:bob@example.com').
        tuples: List of PresenceTuple elements for this presentity.
    """

    entity: str
    tuples: list[PresenceTuple] = field(default_factory=list)

    # ------------------------------------------------------------------
    # PIDF XML Parsing (RFC 3858)
    # ------------------------------------------------------------------

    @classmethod
    def from_pidf(cls, pidf_xml: str) -> PresenceEventPackage:
        """Parse a PIDF XML document into a PresenceEventPackage.

        Args:
            pidf_xml: PIDF XML string per RFC 3858.

        Returns:
            A PresenceEventPackage populated from the PIDF document.

        Raises:
            ProtocolError: If the XML is malformed, missing required
                elements, or uses an incorrect namespace.
        """
        try:
            root = ET.fromstring(pidf_xml)
        except ET.ParseError as exc:
            raise ProtocolError(
                f"Malformed PIDF XML: {exc}",
                rfc_ref="RFC 3858 §2",
            ) from exc

        # Validate namespace
        ns = f"{{{PIDF_NS}}}"
        if root.tag != f"{ns}presence":
            raise ProtocolError(
                f"PIDF root element must be '{ns}presence', got {root.tag!r}",
                rfc_ref="RFC 3858 §2.1",
            )

        # Extract entity attribute
        entity = root.get("entity")
        if not entity:
            raise ProtocolError(
                "PIDF <presence> element missing required 'entity' attribute",
                rfc_ref="RFC 3858 §2.1",
            )

        # Parse tuples
        tuples: list[PresenceTuple] = []
        for tuple_elem in root.findall(f"{ns}tuple"):
            tuple_id = tuple_elem.get("id")
            if not tuple_id:
                raise ProtocolError(
                    "PIDF <tuple> element missing required 'id' attribute",
                    rfc_ref="RFC 3858 §2.2",
                )

            # Parse status/basic
            status = "closed"
            status_elem = tuple_elem.find(f"{ns}status")
            if status_elem is not None:
                basic_elem = status_elem.find(f"{ns}basic")
                if basic_elem is not None and basic_elem.text:
                    status = basic_elem.text.strip()

            # Parse contact
            contact = ""
            contact_elem = tuple_elem.find(f"{ns}contact")
            if contact_elem is not None and contact_elem.text:
                contact = contact_elem.text.strip()

            # Parse note
            note = ""
            note_elem = tuple_elem.find(f"{ns}note")
            if note_elem is not None and note_elem.text:
                note = note_elem.text.strip()

            tuples.append(
                PresenceTuple(
                    id=tuple_id,
                    status=status,
                    contact=contact,
                    note=note,
                )
            )

        return cls(entity=entity, tuples=tuples)

    # ------------------------------------------------------------------
    # PIDF XML Generation (RFC 3858)
    # ------------------------------------------------------------------

    def to_pidf(self) -> str:
        """Generate a PIDF XML document from this presence package.

        Returns:
            PIDF XML string per RFC 3858.
        """
        ET.register_namespace("", PIDF_NS)
        root = ET.Element(f"{{{PIDF_NS}}}presence")
        root.set("entity", self.entity)

        for tup in self.tuples:
            tuple_elem = ET.SubElement(root, f"{{{PIDF_NS}}}tuple")
            tuple_elem.set("id", tup.id)

            status_elem = ET.SubElement(tuple_elem, f"{{{PIDF_NS}}}status")
            basic_elem = ET.SubElement(status_elem, f"{{{PIDF_NS}}}basic")
            basic_elem.text = tup.status

            if tup.contact:
                contact_elem = ET.SubElement(tuple_elem, f"{{{PIDF_NS}}}contact")
                contact_elem.text = tup.contact

            if tup.note:
                note_elem = ET.SubElement(tuple_elem, f"{{{PIDF_NS}}}note")
                note_elem.text = tup.note

        return ET.tostring(root, encoding="unicode", xml_declaration=True)

    # ------------------------------------------------------------------
    # Presence State
    # ------------------------------------------------------------------

    @property
    def overall_state(self) -> str:
        """Derive the overall presence state from all tuples.

        If any tuple is open, the overall state reflects the most
        specific open state. If all tuples are closed, the state is
        'offline'. If no tuples exist, the state is 'unknown'.
        """
        if not self.tuples:
            return "unknown"

        open_tuples = [t for t in self.tuples if t.is_open]
        if not open_tuples:
            return "offline"

        # Return the most specific state from open tuples
        for tup in open_tuples:
            state = tup.presence_state
            if state not in ("online", "offline"):
                return state
        return "online"

    def find_tuple(self, tuple_id: str) -> PresenceTuple | None:
        """Find a tuple by its ID.

        Args:
            tuple_id: The tuple identifier to search for.

        Returns:
            The matching PresenceTuple, or None if not found.
        """
        for tup in self.tuples:
            if tup.id == tuple_id:
                return tup
        return None

    # ------------------------------------------------------------------
    # SUBSCRIBE / NOTIFY Integration (RFC 3856)
    # ------------------------------------------------------------------

    @classmethod
    def create_subscription(
        cls,
        subscriber_uri: str,
        notifier_uri: str,
        call_id: str,
        expires: int = 3600,
    ) -> SubscriptionDialog:
        """Create a presence subscription dialog per RFC 3856.

        Args:
            subscriber_uri: URI of the subscribing user agent.
            notifier_uri: URI of the notifying presentity.
            call_id: SIP Call-ID for the subscription.
            expires: Subscription expiry in seconds.

        Returns:
            A SubscriptionDialog configured for the presence event package.
        """
        from sipx.protocol.dialog import DialogId

        return SubscriptionDialog(
            dialog_id=DialogId(
                call_id=call_id,
                local_tag="",
                remote_tag="",
            ),
            local_uri=subscriber_uri,
            remote_uri=notifier_uri,
            remote_target=notifier_uri,
            local_cseq=0,
            event=PRESENCE_EVENT_PACKAGE,
            expires=expires,
        )

    def build_notify_body(self) -> bytes:
        """Build the PIDF XML body for a NOTIFY request.

        Returns:
            PIDF XML as bytes suitable for a NOTIFY body.
        """
        return self.to_pidf().encode("utf-8")

    def build_notify_request(
        self,
        dialog: SubscriptionDialog,
        state: SubscriptionState | None = None,
    ) -> Request:
        """Build a NOTIFY request carrying this presence information.

        Args:
            dialog: The subscription dialog to build the NOTIFY within.
            state: Optional subscription state override.

        Returns:
            A SIP NOTIFY Request with PIDF XML body.
        """
        sub_state = state or SubscriptionState(dialog.state)
        headers: dict[str, str] = {
            "Event": dialog.event,
            "Subscription-State": sub_state.value,
            "Call-ID": dialog.dialog_id.call_id,
            "From": dialog.remote_uri,
            "To": dialog.local_uri,
            "Content-Type": "application/pidf+xml",
        }
        body = self.build_notify_body()
        return Request(
            method="NOTIFY",
            uri=dialog.local_uri,
            headers=headers,
            body=body,
        )

    @classmethod
    def parse_notify(cls, request: Request) -> PresenceEventPackage:
        """Parse presence information from a NOTIFY request.

        Args:
            request: A SIP NOTIFY request with PIDF XML body.

        Returns:
            A PresenceEventPackage parsed from the NOTIFY body.

        Raises:
            ProtocolError: If the request has no body or the body
                is not valid PIDF XML.
        """
        if not request.body:
            raise ProtocolError(
                "NOTIFY request has no body",
                rfc_ref="RFC 3856 §4.2",
            )

        content_type = request.headers.get("Content-Type", "")
        if isinstance(content_type, list):
            content_type = content_type[0] if content_type else ""

        if "pidf+xml" not in content_type and "application/pidf" not in content_type:
            # Be lenient — try to parse anyway if body looks like XML
            body_str = request.body.decode("utf-8", errors="replace")
            if not body_str.strip().startswith(
                "<?xml"
            ) and not body_str.strip().startswith("<"):
                raise ProtocolError(
                    f"NOTIFY body Content-Type is {content_type!r}, "
                    "expected application/pidf+xml",
                    rfc_ref="RFC 3856 §4.2",
                )

        body_str = request.body.decode("utf-8", errors="replace")
        return cls.from_pidf(body_str)

    @classmethod
    def validate_subscribe(cls, request: Request) -> None:
        """Validate a SUBSCRIBE request for the presence event package.

        Checks that the request has the required Event header with
        value 'presence' per RFC 3856 §4.1.

        Args:
            request: A SIP SUBSCRIBE request to validate.

        Raises:
            ProtocolError: If the request is not a valid presence
                subscription.
        """
        event = request.headers.get("Event", "")
        if isinstance(event, list):
            event = event[0] if event else ""

        if not event:
            raise ProtocolError(
                "SUBSCRIBE request missing required Event header",
                rfc_ref="RFC 3856 §4.1",
            )

        # Event header may contain parameters: "presence;param=value"
        event_name = event.split(";")[0].strip().lower()
        if event_name != PRESENCE_EVENT_PACKAGE:
            raise ProtocolError(
                f"Event header value {event_name!r} is not '{PRESENCE_EVENT_PACKAGE}'",
                rfc_ref="RFC 3856 §4.1",
            )
