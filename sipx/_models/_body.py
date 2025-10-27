"""
SIP Message Body Models and Parsers.

Supports various content types including SDP, text, multipart, and application-specific formats.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ============================================================================
# Base Classes
# ============================================================================


class MessageBody(ABC):
    """Base class for SIP message bodies."""

    @abstractmethod
    def to_bytes(self) -> bytes:
        """Serialize body to bytes."""
        pass

    @abstractmethod
    def to_string(self) -> str:
        """Serialize body to string."""
        pass

    @property
    @abstractmethod
    def content_type(self) -> str:
        """Return the Content-Type header value for this body."""
        pass


# ============================================================================
# SDP (Session Description Protocol) - RFC 4566
# ============================================================================


@dataclass
class SDPBody(MessageBody):
    """
    Session Description Protocol (RFC 4566).

    Simplified structure with all fields directly in the body.

    Example:
        sdp = SDPBody(
            session_name="SIP Call",
            origin_username="-",
            origin_session_id="123",
            origin_session_version="0",
            connection="IN IP4 192.168.1.100"
        )
        sdp.add_media("audio", 8000, "RTP/AVP", ["0", "8"])
    """

    # Session fields (required - must come first)
    session_name: str
    origin_username: str
    origin_session_id: str
    origin_session_version: str

    # Origin fields (optional with defaults)
    origin_network_type: str = "IN"
    origin_address_type: str = "IP4"
    origin_address: str = "127.0.0.1"

    # Session-level fields (optional)
    version: int = 0
    connection: Optional[str] = None  # c= line
    session_info: Optional[str] = None  # i= line
    uri: Optional[str] = None  # u= line
    email: Optional[str] = None  # e= line
    phone: Optional[str] = None  # p= line
    bandwidth: Dict[str, int] = field(default_factory=dict)  # b= lines
    timing: List[str] = field(
        default_factory=lambda: ["0 0"]
    )  # t= lines (required, default to "0 0")
    repeat_times: List[str] = field(default_factory=list)  # r= lines
    time_zones: Optional[str] = None  # z= line
    encryption_key: Optional[str] = None  # k= line
    attributes: Dict[str, Optional[str]] = field(default_factory=dict)  # a= lines

    # Media descriptions (list of dicts)
    media_descriptions: List[Dict[str, Any]] = field(default_factory=list)

    def add_media(
        self,
        media: str,
        port: int,
        protocol: str,
        formats: List[str],
        *,
        port_count: int = 1,
        connection: Optional[str] = None,
        title: Optional[str] = None,
        bandwidth: Optional[Dict[str, int]] = None,
        attributes: Optional[Dict[str, Optional[str]]] = None,
    ) -> None:
        """
        Add a media description.

        Args:
            media: Media type ("audio", "video", "application", etc.)
            port: Port number
            protocol: Protocol ("RTP/AVP", "RTP/SAVP", "UDP", etc.)
            formats: Format list (e.g., payload types)
            port_count: Number of ports (default: 1)
            connection: Media-level connection (optional)
            title: Media title (i= line, optional)
            bandwidth: Bandwidth info (optional)
            attributes: Media attributes (optional)
        """
        media_desc = {
            "media": media,
            "port": port,
            "protocol": protocol,
            "formats": formats,
            "port_count": port_count,
            "connection": connection,
            "title": title,
            "bandwidth": bandwidth or {},
            "attributes": attributes or {},
        }
        self.media_descriptions.append(media_desc)

    def add_attribute(self, name: str, value: Optional[str] = None) -> None:
        """Add a session-level attribute."""
        self.attributes[name] = value

    def to_lines(self) -> List[str]:
        """Convert SDP to list of lines."""
        lines = []

        # Version (required, always first)
        lines.append(f"v={self.version}")

        # Origin (required)
        origin_line = f"o={self.origin_username} {self.origin_session_id} {self.origin_session_version} {self.origin_network_type} {self.origin_address_type} {self.origin_address}"
        lines.append(origin_line)

        # Session Name (required)
        lines.append(f"s={self.session_name}")

        # Session Information (optional)
        if self.session_info:
            lines.append(f"i={self.session_info}")

        # URI (optional)
        if self.uri:
            lines.append(f"u={self.uri}")

        # Email (optional)
        if self.email:
            lines.append(f"e={self.email}")

        # Phone (optional)
        if self.phone:
            lines.append(f"p={self.phone}")

        # Connection (optional but common)
        if self.connection:
            lines.append(f"c={self.connection}")

        # Bandwidth (optional)
        for bw_type, value in self.bandwidth.items():
            lines.append(f"b={bw_type}:{value}")

        # Timing (required)
        for timing in self.timing:
            lines.append(f"t={timing}")

        # Repeat Times (optional)
        for repeat in self.repeat_times:
            lines.append(f"r={repeat}")

        # Time Zones (optional)
        if self.time_zones:
            lines.append(f"z={self.time_zones}")

        # Encryption Key (optional)
        if self.encryption_key:
            lines.append(f"k={self.encryption_key}")

        # Session-level Attributes (optional)
        for attr, value in self.attributes.items():
            if value is None:
                lines.append(f"a={attr}")
            else:
                lines.append(f"a={attr}:{value}")

        # Media Descriptions (optional but common)
        for media in self.media_descriptions:
            # m= line
            port_str = (
                f"{media['port']}/{media['port_count']}"
                if media["port_count"] > 1
                else str(media["port"])
            )
            formats_str = " ".join(media["formats"])
            lines.append(
                f"m={media['media']} {port_str} {media['protocol']} {formats_str}"
            )

            # i= line (title)
            if media.get("title"):
                lines.append(f"i={media['title']}")

            # c= line (media-level connection)
            if media.get("connection"):
                lines.append(f"c={media['connection']}")

            # b= lines (media-level bandwidth)
            for bw_type, value in media.get("bandwidth", {}).items():
                lines.append(f"b={bw_type}:{value}")

            # a= lines (media attributes)
            for attr, value in media.get("attributes", {}).items():
                if value is None:
                    lines.append(f"a={attr}")
                else:
                    lines.append(f"a={attr}:{value}")

        return lines

    def to_string(self) -> str:
        """Serialize SDP to string with CRLF line endings."""
        return "\r\n".join(self.to_lines()) + "\r\n"

    def to_bytes(self) -> bytes:
        """Serialize SDP to bytes."""
        return self.to_string().encode("utf-8")

    def __str__(self) -> str:
        """Return string representation (serialized SDP)."""
        return self.to_string()

    @property
    def content_type(self) -> str:
        """Return Content-Type for SDP."""
        return "application/sdp"

    # ========================================================================
    # Offer/Answer Negotiation (RFC 3264)
    # ========================================================================

    @classmethod
    def create_offer(
        cls,
        session_name: str,
        origin_username: str,
        origin_address: str,
        connection_address: str,
        media_specs: List[Dict[str, Any]],
        *,
        session_id: Optional[str] = None,
        session_version: str = "0",
        attributes: Optional[Dict[str, Optional[str]]] = None,
    ) -> "SDPBody":
        """
        Create an SDP offer for media negotiation.

        Args:
            session_name: Session name
            origin_username: Originator username (use "-" for anonymous)
            origin_address: Originator IP address
            connection_address: Connection IP address
            media_specs: List of media specifications, each dict with:
                - media: Media type ("audio", "video", etc.)
                - port: Port number
                - protocol: Protocol (default "RTP/AVP")
                - codecs: List of codec dicts with 'payload', 'name', 'rate', optional 'params'
                - attributes: Optional dict of media attributes
            session_id: Session ID (auto-generated if not provided)
            session_version: Session version (default "0")
            attributes: Session-level attributes

        Returns:
            SDPBody offer instance

        Example:
            >>> offer = SDPBody.create_offer(
            ...     session_name="VoIP Call",
            ...     origin_username="alice",
            ...     origin_address="192.168.1.100",
            ...     connection_address="192.168.1.100",
            ...     media_specs=[
            ...         {
            ...             "media": "audio",
            ...             "port": 49170,
            ...             "codecs": [
            ...                 {"payload": "0", "name": "PCMU", "rate": "8000"},
            ...                 {"payload": "8", "name": "PCMA", "rate": "8000"},
            ...                 {"payload": "101", "name": "telephone-event", "rate": "8000"}
            ...             ]
            ...         },
            ...         {
            ...             "media": "video",
            ...             "port": 51372,
            ...             "codecs": [
            ...                 {"payload": "31", "name": "H261", "rate": "90000"},
            ...                 {"payload": "34", "name": "H263", "rate": "90000"}
            ...             ]
            ...         }
            ...     ]
            ... )
        """
        # Generate session ID if not provided
        if session_id is None:
            from time import time

            session_id = str(int(time()))

        # Create SDP body
        sdp = cls(
            session_name=session_name,
            origin_username=origin_username,
            origin_session_id=session_id,
            origin_session_version=session_version,
            origin_address=origin_address,
            connection=f"IN IP4 {connection_address}",
            attributes=attributes or {},
        )

        # Add media descriptions
        for spec in media_specs:
            media_type = spec["media"]
            port = spec["port"]
            protocol = spec.get("protocol", "RTP/AVP")
            codecs = spec["codecs"]

            # Extract payload types
            formats = [codec["payload"] for codec in codecs]

            # Build media attributes
            media_attrs = {}

            # Add rtpmap for each codec
            for codec in codecs:
                payload = codec["payload"]
                name = codec["name"]
                rate = codec["rate"]
                params = codec.get("params")

                if params:
                    media_attrs[f"rtpmap:{payload}"] = f"{name}/{rate}/{params}"
                else:
                    media_attrs[f"rtpmap:{payload}"] = f"{name}/{rate}"

                # Add fmtp if provided
                if "fmtp" in codec:
                    media_attrs[f"fmtp:{payload}"] = codec["fmtp"]

            # Add custom attributes
            if "attributes" in spec:
                media_attrs.update(spec["attributes"])

            # Add media description
            sdp.add_media(
                media=media_type,
                port=port,
                protocol=protocol,
                formats=formats,
                connection=spec.get("connection"),
                attributes=media_attrs,
            )

        return sdp

    def create_answer(
        self,
        origin_username: str,
        origin_address: str,
        connection_address: str,
        accepted_media: Optional[List[Dict[str, Any]]] = None,
        *,
        session_version: Optional[str] = None,
    ) -> "SDPBody":
        """
        Create an SDP answer in response to this offer.

        Args:
            origin_username: Answerer username
            origin_address: Answerer IP address
            connection_address: Answerer connection address
            accepted_media: List of accepted media specs (if None, accepts all offered media)
                Each dict should contain:
                - index: Index of offered media (0-based)
                - port: Port to use (0 to reject)
                - codecs: List of accepted codec payloads (subset of offered)
                - attributes: Optional additional attributes
            session_version: Session version (auto-incremented if not provided)

        Returns:
            SDPBody answer instance

        Example:
            >>> # Accept audio with PCMA codec, reject video
            >>> answer = offer.create_answer(
            ...     origin_username="bob",
            ...     origin_address="192.168.1.200",
            ...     connection_address="192.168.1.200",
            ...     accepted_media=[
            ...         {"index": 0, "port": 52000, "codecs": ["8", "101"]},  # Accept audio
            ...         {"index": 1, "port": 0}  # Reject video
            ...     ]
            ... )
        """
        # Increment session version
        if session_version is None:
            session_version = str(int(self.origin_session_version) + 1)

        # Create answer SDP
        from time import time

        answer = SDPBody(
            session_name=self.session_name,
            origin_username=origin_username,
            origin_session_id=str(int(time())),
            origin_session_version=session_version,
            origin_address=origin_address,
            connection=f"IN IP4 {connection_address}",
            attributes=self.attributes.copy(),
        )

        # Process media descriptions
        if accepted_media is None:
            # Accept all media with all codecs by default
            accepted_media = [
                {"index": i, "port": media["port"], "codecs": media["formats"]}
                for i, media in enumerate(self.media_descriptions)
            ]

        for accept_spec in accepted_media:
            idx = accept_spec["index"]
            if idx >= len(self.media_descriptions):
                continue

            offered_media = self.media_descriptions[idx]
            port = accept_spec.get("port", offered_media["port"])
            codecs = accept_spec.get("codecs", offered_media["formats"])

            # Filter codecs to only those offered
            accepted_codecs = [c for c in codecs if c in offered_media["formats"]]

            # Build media attributes (filter to accepted codecs)
            media_attrs = {}
            for attr_key, attr_value in offered_media.get("attributes", {}).items():
                # Copy rtpmap and fmtp only for accepted codecs
                if attr_key.startswith("rtpmap:") or attr_key.startswith("fmtp:"):
                    payload = attr_key.split(":")[1]
                    if payload in accepted_codecs:
                        media_attrs[attr_key] = attr_value
                else:
                    # Copy other attributes
                    media_attrs[attr_key] = attr_value

            # Add custom attributes from accept spec
            if "attributes" in accept_spec:
                media_attrs.update(accept_spec["attributes"])

            # Add media description
            answer.add_media(
                media=offered_media["media"],
                port=port,
                protocol=offered_media["protocol"],
                formats=accepted_codecs if port > 0 else ["0"],  # Port 0 = rejected
                connection=accept_spec.get("connection"),
                attributes=media_attrs,
            )

        return answer

    def modify_session(
        self,
        origin_username: str,
        origin_address: str,
        connection_address: str,
        media_modifications: List[Dict[str, Any]],
        *,
        session_version: Optional[str] = None,
    ) -> "SDPBody":
        """
        Create a modified SDP for re-INVITE or UPDATE (RFC 3311).

        Used to add/remove media streams or change parameters during active session.

        Args:
            origin_username: Origin username
            origin_address: Origin IP address
            connection_address: Connection address
            media_modifications: List of media modification specs:
                - action: "keep", "add", "remove", "modify"
                - index: Index of media (for keep/remove/modify)
                - media: Media type (for add)
                - port: Port number
                - codecs: Codec list
                - attributes: Media attributes
            session_version: Session version (auto-incremented if not provided)

        Returns:
            Modified SDPBody instance

        Example:
            >>> # Add video to audio-only session
            >>> modified = current_sdp.modify_session(
            ...     origin_username="alice",
            ...     origin_address="192.168.1.100",
            ...     connection_address="192.168.1.100",
            ...     media_modifications=[
            ...         {"action": "keep", "index": 0},  # Keep audio
            ...         {
            ...             "action": "add",
            ...             "media": "video",
            ...             "port": 51372,
            ...             "codecs": [
            ...                 {"payload": "31", "name": "H261", "rate": "90000"}
            ...             ]
            ...         }
            ...     ]
            ... )
        """
        # Increment session version
        if session_version is None:
            session_version = str(int(self.origin_session_version) + 1)

        # Create modified SDP
        modified = SDPBody(
            session_name=self.session_name,
            origin_username=origin_username,
            origin_session_id=self.origin_session_id,  # Keep same session ID
            origin_session_version=session_version,
            origin_address=origin_address,
            connection=f"IN IP4 {connection_address}",
            attributes=self.attributes.copy(),
        )

        # Process modifications
        for mod in media_modifications:
            action = mod["action"]

            if action == "keep":
                # Keep existing media unchanged
                idx = mod["index"]
                if idx < len(self.media_descriptions):
                    original = self.media_descriptions[idx]
                    modified.add_media(
                        media=original["media"],
                        port=original["port"],
                        protocol=original["protocol"],
                        formats=original["formats"],
                        connection=original.get("connection"),
                        attributes=original.get("attributes", {}).copy(),
                    )

            elif action == "remove":
                # Remove media (set port to 0)
                idx = mod["index"]
                if idx < len(self.media_descriptions):
                    original = self.media_descriptions[idx]
                    modified.add_media(
                        media=original["media"],
                        port=0,  # Port 0 = removed
                        protocol=original["protocol"],
                        formats=["0"],
                    )

            elif action == "modify":
                # Modify existing media
                idx = mod["index"]
                if idx < len(self.media_descriptions):
                    original = self.media_descriptions[idx]
                    modified.add_media(
                        media=original["media"],
                        port=mod.get("port", original["port"]),
                        protocol=mod.get("protocol", original["protocol"]),
                        formats=mod.get("codecs", original["formats"]),
                        connection=mod.get("connection", original.get("connection")),
                        attributes=mod.get(
                            "attributes", original.get("attributes", {}).copy()
                        ),
                    )

            elif action == "add":
                # Add new media
                media_type = mod["media"]
                port = mod["port"]
                protocol = mod.get("protocol", "RTP/AVP")
                codecs = mod.get("codecs", [])

                # Build formats and attributes
                if isinstance(codecs[0], dict):
                    # Codec specs with details
                    formats = [c["payload"] for c in codecs]
                    media_attrs = {}
                    for codec in codecs:
                        payload = codec["payload"]
                        name = codec["name"]
                        rate = codec["rate"]
                        params = codec.get("params")
                        if params:
                            media_attrs[f"rtpmap:{payload}"] = f"{name}/{rate}/{params}"
                        else:
                            media_attrs[f"rtpmap:{payload}"] = f"{name}/{rate}"
                else:
                    # Just payload numbers
                    formats = codecs
                    media_attrs = mod.get("attributes", {})

                modified.add_media(
                    media=media_type,
                    port=port,
                    protocol=protocol,
                    formats=formats,
                    connection=mod.get("connection"),
                    attributes=media_attrs,
                )

        return modified

    def get_accepted_codecs(self, media_index: int = 0) -> List[Dict[str, str]]:
        """
        Extract accepted codec information from a media description.

        Args:
            media_index: Index of media description (default: 0 for first media)

        Returns:
            List of codec dicts with 'payload', 'name', 'rate', 'params' (if any)

        Example:
            >>> codecs = answer.get_accepted_codecs(0)
            >>> for codec in codecs:
            ...     print(f"{codec['name']} (payload {codec['payload']})")
        """
        if media_index >= len(self.media_descriptions):
            return []

        media = self.media_descriptions[media_index]
        formats = media["formats"]
        attributes = media.get("attributes", {})

        codecs = []
        for payload in formats:
            codec_info = {"payload": payload}

            # Look for rtpmap
            rtpmap_key = f"rtpmap:{payload}"
            if rtpmap_key in attributes:
                rtpmap = attributes[rtpmap_key]
                # Parse "name/rate" or "name/rate/params"
                parts = rtpmap.split("/")
                codec_info["name"] = parts[0]
                if len(parts) > 1:
                    codec_info["rate"] = parts[1]
                if len(parts) > 2:
                    codec_info["params"] = parts[2]

            # Look for fmtp
            fmtp_key = f"fmtp:{payload}"
            if fmtp_key in attributes:
                codec_info["fmtp"] = attributes[fmtp_key]

            codecs.append(codec_info)

        return codecs

    def is_media_rejected(self, media_index: int = 0) -> bool:
        """
        Check if a media stream has been rejected (port = 0).

        Args:
            media_index: Index of media description

        Returns:
            True if media is rejected, False otherwise
        """
        if media_index >= len(self.media_descriptions):
            return True

        return self.media_descriptions[media_index]["port"] == 0


# ============================================================================
# Text Bodies
# ============================================================================


@dataclass
class TextBody(MessageBody):
    """Plain text message body (text/plain)."""

    text: str
    charset: str = "utf-8"

    def to_string(self) -> str:
        return self.text

    def to_bytes(self) -> bytes:
        return self.text.encode(self.charset)

    def __str__(self) -> str:
        """Return string representation (serialized text)."""
        return self.to_string()

    @property
    def content_type(self) -> str:
        return f"text/plain; charset={self.charset}"


@dataclass
class HTMLBody(MessageBody):
    """HTML message body (text/html)."""

    html: str
    charset: str = "utf-8"

    def to_string(self) -> str:
        return self.html

    def to_bytes(self) -> bytes:
        return self.html.encode(self.charset)

    def __str__(self) -> str:
        """Return string representation (serialized HTML)."""
        return self.to_string()

    @property
    def content_type(self) -> str:
        return f"text/html; charset={self.charset}"


# ============================================================================
# DTMF Bodies
# ============================================================================


@dataclass
class DTMFRelayBody(MessageBody):
    """DTMF relay message body (application/dtmf-relay)."""

    signal: str  # DTMF digit (0-9, *, #, A-D)
    duration: Optional[int] = None  # Duration in milliseconds

    def to_string(self) -> str:
        if self.duration:
            return f"Signal={self.signal}\r\nDuration={self.duration}\r\n"
        return f"Signal={self.signal}\r\n"

    def to_bytes(self) -> bytes:
        return self.to_string().encode("utf-8")

    def __str__(self) -> str:
        """Return string representation (serialized DTMF relay)."""
        return self.to_string()

    @property
    def content_type(self) -> str:
        return "application/dtmf-relay"


@dataclass
class DTMFBody(MessageBody):
    """DTMF message body (application/dtmf)."""

    signal: str  # DTMF digit (0-9, *, #, A-D)
    duration: Optional[int] = None  # Duration in milliseconds

    def to_string(self) -> str:
        if self.duration:
            return f"Signal={self.signal}\r\nDuration={self.duration}\r\n"
        return f"Signal={self.signal}\r\n"

    def to_bytes(self) -> bytes:
        return self.to_string().encode("utf-8")

    def __str__(self) -> str:
        """Return string representation (serialized DTMF)."""
        return self.to_string()

    @property
    def content_type(self) -> str:
        return "application/dtmf"


# ============================================================================
# SIP Fragment Bodies
# ============================================================================


@dataclass
class SIPFragBody(MessageBody):
    """SIP message fragment body (message/sipfrag)."""

    fragment: str  # Partial SIP message

    def to_string(self) -> str:
        return self.fragment

    def to_bytes(self) -> bytes:
        return self.fragment.encode("utf-8")

    def __str__(self) -> str:
        """Return string representation (serialized SIP fragment)."""
        return self.to_string()

    @property
    def content_type(self) -> str:
        return "message/sipfrag"


# ============================================================================
# XML Bodies
# ============================================================================


@dataclass
class XMLBody(MessageBody):
    """Generic XML body for various application/xxx+xml types."""

    xml: str
    subtype: str  # e.g., "pidf+xml", "conference-info+xml", "dialog-info+xml"
    charset: str = "utf-8"

    def to_string(self) -> str:
        return self.xml

    def to_bytes(self) -> bytes:
        return self.xml.encode(self.charset)

    def __str__(self) -> str:
        """Return string representation (serialized XML)."""
        return self.to_string()

    @property
    def content_type(self) -> str:
        return f"application/{self.subtype}+xml; charset={self.charset}"


@dataclass
class PIDFBody(MessageBody):
    """
    Presence Information Data Format (PIDF) body (application/pidf+xml).

    RFC 3863 - Presence Information Data Format (PIDF)
    Used for SIP PUBLISH/NOTIFY presence functionality.
    """

    xml: str
    charset: str = "utf-8"

    def to_string(self) -> str:
        return self.xml

    def to_bytes(self) -> bytes:
        return self.xml.encode(self.charset)

    def __str__(self) -> str:
        """Return string representation (serialized PIDF)."""
        return self.to_string()

    @property
    def content_type(self) -> str:
        return f"application/pidf+xml; charset={self.charset}"


@dataclass
class ConferenceInfoBody(MessageBody):
    """
    Conference information body (application/conference-info+xml).

    RFC 4575 - Conference Event Package
    Used for conference state notifications.
    """

    xml: str
    charset: str = "utf-8"

    def to_string(self) -> str:
        return self.xml

    def to_bytes(self) -> bytes:
        return self.xml.encode(self.charset)

    def __str__(self) -> str:
        """Return string representation (serialized conference info)."""
        return self.to_string()

    @property
    def content_type(self) -> str:
        return f"application/conference-info+xml; charset={self.charset}"


@dataclass
class DialogInfoBody(MessageBody):
    """
    Dialog information body (application/dialog-info+xml).

    RFC 4235 - Dialog Package
    Used for monitoring SIP dialog state.
    """

    xml: str
    charset: str = "utf-8"

    def to_string(self) -> str:
        return self.xml

    def to_bytes(self) -> bytes:
        return self.xml.encode(self.charset)

    def __str__(self) -> str:
        """Return string representation (serialized dialog info)."""
        return self.to_string()

    @property
    def content_type(self) -> str:
        return f"application/dialog-info+xml; charset={self.charset}"


@dataclass
class ResourceListsBody(MessageBody):
    """
    Resource lists body (application/resource-lists+xml).

    RFC 4826 - Resource Lists
    Used for buddy lists and resource collections.
    """

    xml: str
    charset: str = "utf-8"

    def to_string(self) -> str:
        return self.xml

    def to_bytes(self) -> bytes:
        return self.xml.encode(self.charset)

    def __str__(self) -> str:
        """Return string representation (serialized resource lists)."""
        return self.to_string()

    @property
    def content_type(self) -> str:
        return f"application/resource-lists+xml; charset={self.charset}"


# ============================================================================
# ISUP and PSTN Interoperability
# ============================================================================


@dataclass
class ISUPBody(MessageBody):
    """
    ISUP (ISDN User Part) message body (application/isup).

    RFC 3204 - MIME media types for ISUP and QSIG Objects
    Used for PSTN/telephony traditional network interoperability.
    """

    data: bytes  # Binary ISUP message

    def to_string(self) -> str:
        """Return hex representation of ISUP data."""
        return self.data.hex()

    def to_bytes(self) -> bytes:
        return self.data

    def __str__(self) -> str:
        """Return string representation (hex ISUP data)."""
        return self.to_string()

    @property
    def content_type(self) -> str:
        return "application/isup"


# ============================================================================
# Message Summary and Voice Mail
# ============================================================================


@dataclass
class SimpleMsgSummaryBody(MessageBody):
    """
    Simple message summary body (application/simple-message-summary).

    RFC 3842 - Message Summary Event Package
    Used for voice mail and message waiting indicators (MWI).
    """

    messages_waiting: bool = False
    voice_message_new: int = 0
    voice_message_old: int = 0
    voice_message_urgent_new: int = 0
    voice_message_urgent_old: int = 0
    fax_message_new: int = 0
    fax_message_old: int = 0
    email_message_new: int = 0
    email_message_old: int = 0
    account: Optional[str] = None

    def to_string(self) -> str:
        """Serialize to message summary format."""
        lines = []

        lines.append(f"Messages-Waiting: {'yes' if self.messages_waiting else 'no'}")

        if self.account:
            lines.append(f"Message-Account: {self.account}")

        # Voice messages
        if self.voice_message_new > 0 or self.voice_message_old > 0:
            lines.append(
                f"Voice-Message: {self.voice_message_new}/{self.voice_message_old}"
            )

        # Urgent voice messages
        if self.voice_message_urgent_new > 0 or self.voice_message_urgent_old > 0:
            lines.append(
                f"Voice-Message-Urgent: {self.voice_message_urgent_new}/{self.voice_message_urgent_old}"
            )

        # Fax messages
        if self.fax_message_new > 0 or self.fax_message_old > 0:
            lines.append(f"Fax-Message: {self.fax_message_new}/{self.fax_message_old}")

        # Email messages
        if self.email_message_new > 0 or self.email_message_old > 0:
            lines.append(
                f"Email-Message: {self.email_message_new}/{self.email_message_old}"
            )

        return "\r\n".join(lines) + "\r\n"

    def to_bytes(self) -> bytes:
        return self.to_string().encode("utf-8")

    def __str__(self) -> str:
        """Return string representation (serialized message summary)."""
        return self.to_string()

    @property
    def content_type(self) -> str:
        return "application/simple-message-summary"


@dataclass
class RawBody(MessageBody):
    """Raw binary or unknown content type body."""

    data: bytes
    mime_type: str

    def to_string(self) -> str:
        try:
            return self.data.decode("utf-8")
        except UnicodeDecodeError:
            return self.data.decode("latin-1")

    def to_bytes(self) -> bytes:
        return self.data

    def __str__(self) -> str:
        """Return string representation (decoded raw body)."""
        return self.to_string()

    @property
    def content_type(self) -> str:
        return self.mime_type


# ============================================================================
# Multipart Bodies
# ============================================================================


@dataclass
class MultipartBody(MessageBody):
    """Multipart MIME message body (multipart/mixed, etc.)."""

    parts: List[MessageBody] = field(default_factory=list)
    boundary: str = "sipboundary"
    subtype: str = "mixed"  # "mixed", "alternative", "related", etc.

    def add_part(self, part: MessageBody) -> None:
        """Add a body part to the multipart message."""
        self.parts.append(part)

    def to_string(self) -> str:
        """Serialize multipart body to string."""
        lines = []

        for part in self.parts:
            lines.append(f"--{self.boundary}")
            lines.append(f"Content-Type: {part.content_type}")
            lines.append("")  # Empty line between headers and body
            lines.append(part.to_string().rstrip("\r\n"))

        # Final boundary
        lines.append(f"--{self.boundary}--")

        return "\r\n".join(lines) + "\r\n"

    def to_bytes(self) -> bytes:
        """Serialize multipart body to bytes."""
        return self.to_string().encode("utf-8")

    def __str__(self) -> str:
        """Return string representation (serialized multipart body)."""
        return self.to_string()

    @property
    def content_type(self) -> str:
        """Return Content-Type with boundary parameter."""
        return f"multipart/{self.subtype}; boundary={self.boundary}"


# ============================================================================
# Body Parser
# ============================================================================


class BodyParser:
    """Parser for SIP message bodies based on Content-Type."""

    @staticmethod
    def parse(content: bytes, content_type: str) -> MessageBody:
        """
        Parse message body based on Content-Type.

        Args:
            content: Raw body content as bytes
            content_type: Content-Type header value

        Returns:
            Parsed MessageBody subclass instance

        Example:
            body = BodyParser.parse(raw_content, "application/sdp")
        """
        # Normalize content type (lowercase, strip parameters for matching)
        mime_type = content_type.split(";")[0].strip().lower()

        # Route to appropriate parser
        if mime_type == "application/sdp":
            return BodyParser.parse_sdp(content)
        elif mime_type == "text/plain":
            return BodyParser.parse_text(content, content_type)
        elif mime_type == "text/html":
            return BodyParser.parse_html(content, content_type)
        elif mime_type == "application/dtmf-relay":
            return BodyParser.parse_dtmf_relay(content)
        elif mime_type == "application/dtmf":
            return BodyParser.parse_dtmf(content)
        elif mime_type == "message/sipfrag":
            return BodyParser.parse_sipfrag(content)
        elif mime_type == "application/isup":
            return BodyParser.parse_isup(content)
        elif mime_type == "application/simple-message-summary":
            return BodyParser.parse_simple_message_summary(content)
        elif mime_type == "application/pidf+xml":
            return BodyParser.parse_pidf(content, content_type)
        elif mime_type == "application/conference-info+xml":
            return BodyParser.parse_conference_info(content, content_type)
        elif mime_type == "application/dialog-info+xml":
            return BodyParser.parse_dialog_info(content, content_type)
        elif mime_type == "application/resource-lists+xml":
            return BodyParser.parse_resource_lists(content, content_type)
        elif mime_type.startswith("application/") and mime_type.endswith("+xml"):
            return BodyParser.parse_xml(content, mime_type, content_type)
        elif mime_type.startswith("multipart/"):
            return BodyParser.parse_multipart(content, content_type)
        else:
            # Unknown type - store as raw
            return RawBody(data=content, mime_type=mime_type)

    @staticmethod
    def parse_sdp(content: bytes) -> SDPBody:
        """Parse SDP body from bytes."""
        text = content.decode("utf-8")
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # Required fields
        origin_username = "-"
        origin_session_id = "0"
        origin_session_version = "0"
        origin_network_type = "IN"
        origin_address_type = "IP4"
        origin_address = "127.0.0.1"
        session_name = ""
        version = 0

        # Optional fields
        connection = None
        session_info = None
        uri = None
        email = None
        phone = None
        bandwidth: Dict[str, int] = {}
        timing: List[str] = []
        repeat_times: List[str] = []
        time_zones = None
        encryption_key = None
        attributes: Dict[str, Optional[str]] = {}
        media_descriptions: List[Dict[str, Any]] = []

        current_media: Optional[Dict[str, Any]] = None

        for line in lines:
            if not line or "=" not in line:
                continue

            field_type = line[0]
            field_value = line[2:].strip()  # Skip "X=" prefix

            # Session-level fields
            if field_type == "v":
                version = int(field_value)

            elif field_type == "o":
                parts = field_value.split()
                if len(parts) >= 6:
                    origin_username = parts[0]
                    origin_session_id = parts[1]
                    origin_session_version = parts[2]
                    origin_network_type = parts[3]
                    origin_address_type = parts[4]
                    origin_address = parts[5]

            elif field_type == "s":
                session_name = field_value

            elif field_type == "i":
                if current_media:
                    current_media["title"] = field_value
                else:
                    session_info = field_value

            elif field_type == "u":
                uri = field_value

            elif field_type == "e":
                email = field_value

            elif field_type == "p":
                phone = field_value

            elif field_type == "c":
                if current_media:
                    current_media["connection"] = field_value
                else:
                    connection = field_value

            elif field_type == "b":
                if ":" in field_value:
                    bw_type, bw_value = field_value.split(":", 1)
                    bw_dict = current_media["bandwidth"] if current_media else bandwidth
                    bw_dict[bw_type] = int(bw_value)

            elif field_type == "t":
                timing.append(field_value)

            elif field_type == "r":
                repeat_times.append(field_value)

            elif field_type == "z":
                time_zones = field_value

            elif field_type == "k":
                encryption_key = field_value

            elif field_type == "a":
                # Attribute line
                if ":" in field_value:
                    attr_name, attr_value = field_value.split(":", 1)
                else:
                    attr_name = field_value
                    attr_value = None

                if current_media:
                    current_media["attributes"][attr_name] = attr_value
                else:
                    attributes[attr_name] = attr_value

            elif field_type == "m":
                # Save previous media if exists
                if current_media:
                    media_descriptions.append(current_media)

                # Parse media line: m=<media> <port>[/<count>] <proto> <fmt> ...
                parts = field_value.split()
                if len(parts) >= 4:
                    media_type = parts[0]
                    port_spec = parts[1]
                    protocol = parts[2]
                    formats = parts[3:]

                    # Parse port and optional port count
                    if "/" in port_spec:
                        port_str, count_str = port_spec.split("/", 1)
                        port = int(port_str)
                        port_count = int(count_str)
                    else:
                        port = int(port_spec)
                        port_count = 1

                    current_media = {
                        "media": media_type,
                        "port": port,
                        "protocol": protocol,
                        "formats": formats,
                        "port_count": port_count,
                        "connection": None,
                        "title": None,
                        "bandwidth": {},
                        "attributes": {},
                    }

        # Add last media if exists
        if current_media:
            media_descriptions.append(current_media)

        # Create SDP object
        return SDPBody(
            session_name=session_name or "-",
            origin_username=origin_username,
            origin_session_id=origin_session_id,
            origin_session_version=origin_session_version,
            origin_network_type=origin_network_type,
            origin_address_type=origin_address_type,
            origin_address=origin_address,
            version=version,
            connection=connection,
            session_info=session_info,
            uri=uri,
            email=email,
            phone=phone,
            bandwidth=bandwidth,
            timing=timing if timing else ["0 0"],
            repeat_times=repeat_times,
            time_zones=time_zones,
            encryption_key=encryption_key,
            attributes=attributes,
            media_descriptions=media_descriptions,
        )

    @staticmethod
    def parse_text(content: bytes, content_type: str) -> TextBody:
        """Parse plain text body."""
        charset = BodyParser._extract_charset(content_type)
        text = content.decode(charset)
        return TextBody(text=text, charset=charset)

    @staticmethod
    def parse_html(content: bytes, content_type: str) -> HTMLBody:
        """Parse HTML body."""
        charset = BodyParser._extract_charset(content_type)
        html = content.decode(charset)
        return HTMLBody(html=html, charset=charset)

    @staticmethod
    def parse_dtmf_relay(content: bytes) -> DTMFRelayBody:
        """Parse DTMF relay body (application/dtmf-relay)."""
        text = content.decode("utf-8")
        signal = None
        duration = None

        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("Signal="):
                signal = line.split("=", 1)[1].strip()
            elif line.startswith("Duration="):
                duration = int(line.split("=", 1)[1].strip())

        return DTMFRelayBody(signal=signal or "", duration=duration)

    @staticmethod
    def parse_dtmf(content: bytes) -> DTMFBody:
        """Parse DTMF body (application/dtmf)."""
        text = content.decode("utf-8")
        signal = None
        duration = None

        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("Signal="):
                signal = line.split("=", 1)[1].strip()
            elif line.startswith("Duration="):
                duration = int(line.split("=", 1)[1].strip())

        return DTMFBody(signal=signal or "", duration=duration)

    @staticmethod
    def parse_sipfrag(content: bytes) -> SIPFragBody:
        """Parse SIP fragment body."""
        fragment = content.decode("utf-8")
        return SIPFragBody(fragment=fragment)

    @staticmethod
    def parse_xml(content: bytes, mime_type: str, content_type: str) -> XMLBody:
        """Parse generic XML body."""
        charset = BodyParser._extract_charset(content_type)
        xml = content.decode(charset)
        # Extract subtype (e.g., "pidf+xml" from "application/pidf+xml")
        subtype = mime_type.split("/", 1)[1] if "/" in mime_type else "xml"
        return XMLBody(xml=xml, subtype=subtype, charset=charset)

    @staticmethod
    def parse_pidf(content: bytes, content_type: str) -> PIDFBody:
        """Parse PIDF (Presence Information Data Format) body."""
        charset = BodyParser._extract_charset(content_type)
        xml = content.decode(charset)
        return PIDFBody(xml=xml, charset=charset)

    @staticmethod
    def parse_conference_info(content: bytes, content_type: str) -> ConferenceInfoBody:
        """Parse conference-info+xml body."""
        charset = BodyParser._extract_charset(content_type)
        xml = content.decode(charset)
        return ConferenceInfoBody(xml=xml, charset=charset)

    @staticmethod
    def parse_dialog_info(content: bytes, content_type: str) -> DialogInfoBody:
        """Parse dialog-info+xml body."""
        charset = BodyParser._extract_charset(content_type)
        xml = content.decode(charset)
        return DialogInfoBody(xml=xml, charset=charset)

    @staticmethod
    def parse_resource_lists(content: bytes, content_type: str) -> ResourceListsBody:
        """Parse resource-lists+xml body."""
        charset = BodyParser._extract_charset(content_type)
        xml = content.decode(charset)
        return ResourceListsBody(xml=xml, charset=charset)

    @staticmethod
    def parse_isup(content: bytes) -> ISUPBody:
        """Parse ISUP (ISDN User Part) body."""
        return ISUPBody(data=content)

    @staticmethod
    def parse_simple_message_summary(content: bytes) -> SimpleMsgSummaryBody:
        """Parse simple-message-summary body (MWI)."""
        text = content.decode("utf-8")

        messages_waiting = False
        voice_new = 0
        voice_old = 0
        voice_urgent_new = 0
        voice_urgent_old = 0
        fax_new = 0
        fax_old = 0
        email_new = 0
        email_old = 0
        account = None

        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue

            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()

                if key == "Messages-Waiting":
                    messages_waiting = value.lower() in ("yes", "true", "1")
                elif key == "Message-Account":
                    account = value
                elif key == "Voice-Message":
                    if "/" in value:
                        new, old = value.split("/", 1)
                        voice_new = int(new.strip())
                        voice_old = int(old.strip())
                elif key == "Voice-Message-Urgent":
                    if "/" in value:
                        new, old = value.split("/", 1)
                        voice_urgent_new = int(new.strip())
                        voice_urgent_old = int(old.strip())
                elif key == "Fax-Message":
                    if "/" in value:
                        new, old = value.split("/", 1)
                        fax_new = int(new.strip())
                        fax_old = int(old.strip())
                elif key == "Email-Message":
                    if "/" in value:
                        new, old = value.split("/", 1)
                        email_new = int(new.strip())
                        email_old = int(old.strip())

        return SimpleMsgSummaryBody(
            messages_waiting=messages_waiting,
            voice_message_new=voice_new,
            voice_message_old=voice_old,
            voice_message_urgent_new=voice_urgent_new,
            voice_message_urgent_old=voice_urgent_old,
            fax_message_new=fax_new,
            fax_message_old=fax_old,
            email_message_new=email_new,
            email_message_old=email_old,
            account=account,
        )

    @staticmethod
    def parse_multipart(content: bytes, content_type: str) -> MultipartBody:
        """Parse multipart body."""
        # Extract boundary
        boundary = BodyParser._extract_boundary(content_type)
        if not boundary:
            boundary = "boundary"

        # Extract subtype (mixed, alternative, etc.)
        mime_parts = content_type.split(";")[0].strip().lower().split("/")
        subtype = mime_parts[1] if len(mime_parts) > 1 else "mixed"

        text = content.decode("utf-8")
        multipart = MultipartBody(boundary=boundary, subtype=subtype)

        # Split by boundary
        boundary_delimiter = f"--{boundary}"
        parts = text.split(boundary_delimiter)

        for part in parts:
            part = part.strip()
            if not part or part == "--":
                continue

            # Split headers and body
            if "\r\n\r\n" in part:
                headers_section, body_section = part.split("\r\n\r\n", 1)
            elif "\n\n" in part:
                headers_section, body_section = part.split("\n\n", 1)
            else:
                continue

            # Extract Content-Type from part headers
            part_content_type = "text/plain"
            for header_line in headers_section.split("\n"):
                if header_line.lower().startswith("content-type:"):
                    part_content_type = header_line.split(":", 1)[1].strip()
                    break

            # Parse the part recursively
            part_body = BodyParser.parse(
                body_section.encode("utf-8"), part_content_type
            )
            multipart.add_part(part_body)

        return multipart

    @staticmethod
    def _extract_charset(content_type: str) -> str:
        """Extract charset parameter from Content-Type."""
        for param in content_type.split(";"):
            param = param.strip()
            if param.lower().startswith("charset="):
                return param.split("=", 1)[1].strip().strip('"')
        return "utf-8"

    @staticmethod
    def _extract_boundary(content_type: str) -> Optional[str]:
        """Extract boundary parameter from Content-Type."""
        for param in content_type.split(";"):
            param = param.strip()
            if param.lower().startswith("boundary="):
                boundary = param.split("=", 1)[1].strip()
                # Remove quotes if present
                return boundary.strip('"')
        return None


# ============================================================================
# Exports
# ============================================================================


__all__ = [
    # Base class
    "MessageBody",
    # SDP
    "SDPBody",
    # Text bodies
    "TextBody",
    "HTMLBody",
    # DTMF
    "DTMFRelayBody",
    "DTMFBody",
    # SIP Fragment
    "SIPFragBody",
    # XML bodies
    "XMLBody",
    "PIDFBody",
    "ConferenceInfoBody",
    "DialogInfoBody",
    "ResourceListsBody",
    # ISUP/PSTN
    "ISUPBody",
    # Message summary
    "SimpleMsgSummaryBody",
    # Multipart
    "MultipartBody",
    # Raw/unknown
    "RawBody",
    # Parser
    "BodyParser",
]
