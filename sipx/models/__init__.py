"""
SIP Models Package.

This package contains models for SIP messages, headers, and body content.
"""

from ._auth import (
    Auth,
    AuthMethod,
    AuthParser,
    Challenge,
    Credentials,
    DigestAuth,
    DigestChallenge,
    DigestCredentials,
    SipAuthCredentials,
    SIPAuthCredentials,
)
from ._body import (
    BodyParser,
    MessageBody,
    PIFDBody,
    RawBody,
    SDPBody,
)
from ._header import HeaderContainer, HeaderParser, Headers
from ._message import MessageParser, Request, Response, SIPMessage

__all__ = [
    # Headers - Base classes
    "HeaderContainer",
    # Headers - Implementations
    "Headers",
    # Headers - Parser
    "HeaderParser",
    # Messages - Base classes
    "SIPMessage",
    # Messages - Implementations
    "Request",
    "Response",
    # Messages - Parser
    "MessageParser",
    # Authentication - Simplified API
    "Auth",
    # Authentication - Base classes
    "AuthMethod",
    "Challenge",
    "Credentials",
    # Authentication - Digest
    "DigestAuth",
    "DigestChallenge",
    "DigestCredentials",
    # Authentication - Simplified Credentials
    "SipAuthCredentials",
    "SIPAuthCredentials",  # uppercase-SIP canonical alias
    # Authentication - Parser
    "AuthParser",
    # Body types
    "MessageBody",
    "RawBody",
    "BodyParser",
    "SDPBody",
    "PIFDBody",
]
