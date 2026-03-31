"""
Dependency injection extractors for SIP server handlers.

Provides an Extractor ABC and built-in extractors that resolve handler
parameters from SIP requests via ``typing.Annotated`` metadata, similar
to FastAPI's ``Depends``.

Example::

    from typing import Annotated
    from sipx._depends import FromHeader, SDP, AutoRTP

    @server.invite
    def on_invite(
        request: Request,
        caller: Annotated[str, FromHeader()],
        sdp: Annotated[SDPBody, SDP()],
        rtp: Annotated[RTPSession, AutoRTP(port=19000)],
    ) -> Response:
        ...
"""

from __future__ import annotations

import typing
from abc import ABC, abstractmethod
from typing import Any

from ._models._message import Request
from ._types import TransportAddress


# ============================================================================
# Base Extractor
# ============================================================================


class Extractor(ABC):
    """Abstract base class for dependency injection extractors.

    Subclass and implement ``extract`` to create custom extractors
    usable with ``typing.Annotated``.
    """

    @abstractmethod
    def extract(self, request: Request, source: TransportAddress) -> Any:
        """Extract a value from a SIP request and transport source.

        Args:
            request: The incoming SIP request.
            source: The transport address the request arrived from.

        Returns:
            The extracted value to inject into the handler.
        """
        ...


# ============================================================================
# Built-in Extractors
# ============================================================================


class FromHeader(Extractor):
    """Extract the ``From`` header value."""

    def extract(self, request: Request, source: TransportAddress) -> str | None:
        return request.from_header


class ToHeader(Extractor):
    """Extract the ``To`` header value."""

    def extract(self, request: Request, source: TransportAddress) -> str | None:
        return request.to_header


class CallID(Extractor):
    """Extract the ``Call-ID`` header value."""

    def extract(self, request: Request, source: TransportAddress) -> str | None:
        return request.call_id


class CSeqValue(Extractor):
    """Extract the ``CSeq`` header value."""

    def extract(self, request: Request, source: TransportAddress) -> str | None:
        return request.cseq


class ViaValue(Extractor):
    """Extract the ``Via`` header value."""

    def extract(self, request: Request, source: TransportAddress) -> str | None:
        return request.via


class SDP(Extractor):
    """Extract the lazily-parsed SDP body (``SDPBody`` or ``None``)."""

    def extract(self, request: Request, source: TransportAddress) -> Any:
        return request.body


class Source(Extractor):
    """Extract the ``TransportAddress`` the request arrived from."""

    def extract(self, request: Request, source: TransportAddress) -> TransportAddress:
        return source


class Header(Extractor):
    """Extract an arbitrary header by name.

    Args:
        name: The header name to look up.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def extract(self, request: Request, source: TransportAddress) -> str | None:
        return request.headers.get(self.name)


class AutoRTP(Extractor):
    """Create an ``RTPSession`` from the request SDP automatically.

    Args:
        port: Local RTP port to bind.
    """

    def __init__(self, port: int) -> None:
        self.port = port

    def extract(self, request: Request, source: TransportAddress) -> Any:
        from ._media._rtp import RTPSession

        body = request.body
        if body and hasattr(body, "get_rtp_params"):
            return RTPSession.from_sdp(body, source.host, self.port)
        return None


# ============================================================================
# Handler Resolver
# ============================================================================


def resolve_handler(
    handler: Any,
    request: Request,
    source: TransportAddress,
) -> Any:
    """Inspect handler type hints and inject dependencies.

    Reads ``typing.get_type_hints(handler, include_extras=True)`` and
    resolves each parameter:

    * ``Request`` -> the request itself
    * ``TransportAddress`` -> the source address
    * ``Annotated[X, <Extractor>]`` -> calls ``extractor.extract(...)``

    Falls back to ``handler(request, source)`` when no hints match.

    Args:
        handler: The user-defined request handler callable.
        request: The incoming SIP request.
        source: The transport address the request arrived from.

    Returns:
        The return value of the handler invocation.
    """
    hints = typing.get_type_hints(handler, include_extras=True)
    kwargs: dict[str, Any] = {}

    for name, hint in hints.items():
        if name == "return":
            continue

        # Direct type match: Request
        if hint is Request or (
            hasattr(hint, "__name__") and hint.__name__ == "Request"
        ):
            kwargs[name] = request
            continue

        # Direct type match: TransportAddress
        if hint is TransportAddress:
            kwargs[name] = source
            continue

        # Annotated[X, extractor] — look for Extractor in metadata
        if hasattr(hint, "__metadata__"):
            for meta in hint.__metadata__:
                # Accept both instances and classes
                if isinstance(meta, Extractor):
                    kwargs[name] = meta.extract(request, source)
                    break
                if isinstance(meta, type) and issubclass(meta, Extractor):
                    kwargs[name] = meta().extract(request, source)
                    break

    if not kwargs:
        # No type hints matched — old-style handler(request, source)
        return handler(request, source)

    # Fill unresolved params by position (request, source)
    import inspect

    sig = inspect.signature(handler)
    positional = [p.name for p in sig.parameters.values() if p.name != "return"]
    for i, name in enumerate(positional):
        if name not in kwargs:
            if i == 0:
                kwargs[name] = request
            elif i == 1:
                kwargs[name] = source

    return handler(**kwargs)


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "Extractor",
    "FromHeader",
    "ToHeader",
    "CallID",
    "CSeqValue",
    "ViaValue",
    "SDP",
    "Source",
    "Header",
    "AutoRTP",
    "resolve_handler",
]
