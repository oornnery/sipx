"""Utilities and constants for SIP protocol."""

import logging
import typing

if typing.TYPE_CHECKING:
    pass

# Rich Console for pretty printing (lazy init to avoid import overhead)
console: typing.Any = None


def _get_console():
    """Lazily initialize the Rich console."""
    global console
    if console is None:
        from rich.console import Console

        console = Console()
    return console


def _init_console() -> typing.Any:
    """Return the module-level console, initializing it if needed.

    Examples import ``console`` directly from this module.  Because the
    name is bound to ``None`` at parse time, they would get ``None`` unless
    we initialise it eagerly here or they call ``_get_console()`` first.
    This function is called once at module import to ensure ``console`` is
    ready for any importer.
    """
    return _get_console()


# Eagerly initialise so ``from sipx._utils import console`` works immediately.
try:
    console = _init_console()
except Exception:
    # rich may not be installed; fall back to a simple print wrapper
    class _FallbackConsole:  # type: ignore[no-redef]
        """Minimal console replacement when rich is unavailable."""

        def print(self, *args, **kwargs) -> None:  # noqa: A003
            import re

            text = " ".join(str(a) for a in args)
            # Strip rich markup tags like [bold], [green], etc.
            text = re.sub(r"\[/?[^\]]+\]", "", text)
            print(text)

    console = _FallbackConsole()


def configure_logging(
    level: int = logging.INFO,
    *,
    rich: bool = True,
    format: str = "%(message)s",
    datefmt: str = "[%X]",
) -> None:
    """Configure sipx logging.

    This must be called explicitly by the user to set up logging.
    By default sipx does NOT configure logging on import (to avoid
    overwriting the user's configuration).

    Args:
        level: Logging level (default: INFO).
        rich: Use RichHandler for pretty output (default: True).
        format: Log format string.
        datefmt: Date format string.

    Example::

        import sipx
        sipx.configure_logging(level=logging.DEBUG)
    """
    if rich:
        try:
            from rich.logging import RichHandler

            handler = RichHandler(
                console=_get_console(), rich_tracebacks=True, show_path=False
            )
        except ImportError:
            handler = logging.StreamHandler()
    else:
        handler = logging.StreamHandler()

    handler.setFormatter(logging.Formatter(fmt=format, datefmt=datefmt))

    # Avoid duplicate handlers on repeated calls
    root = logging.getLogger("sipx")
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(handler)


# Get logger for the package (user configures it via configure_logging())
logger = logging.getLogger("sipx")

EOL = "\r\n"
SCHEME = "SIP"
VERSION = "2.0"
BRANCH = "z9hG4bK"

# Formas compactas de headers SIP (RFC 3261 Section 7.3.3)
# Mapeia forma compacta -> nome normalizado (minúsculo)
HEADERS_COMPACT = {
    "v": "via",
    "f": "from",
    "t": "to",
    "m": "contact",
    "i": "call-id",
    "e": "content-encoding",
    "l": "content-length",
    "c": "content-type",
    "s": "subject",
    "k": "supported",
    "a": "accept-contact",
    "u": "allow-events",
    "o": "event",
    "y": "identity",
    "b": "referred-by",
    "r": "refer-to",
    "d": "request-disposition",
    "x": "session-expires",
    "j": "reject-contact",
}

# Headers SIP essenciais e mais comuns com suas formas canônicas
# Mapeia nome normalizado (minúsculo) -> forma canônica correta
HEADERS = {
    # Headers obrigatórios RFC 3261
    # Headers com canonização especial (não seguem Title-Case simples)
    "call-id": "Call-ID",
    "cseq": "CSeq",
    "www-authenticate": "WWW-Authenticate",
    "proxy-authenticate": "Proxy-Authenticate",
    "rack": "RAck",
    "rseq": "RSeq",
    "sip-etag": "SIP-ETag",
    "sip-if-match": "SIP-If-Match",
    "mime-version": "MIME-Version",
    "min-se": "Min-SE",
    "content-id": "Content-ID",
    "session-id": "Session-ID",
    "policy-id": "Policy-ID",
    "via": "Via",
    "from": "From",
    "to": "To",
    "max-forwards": "Max-Forwards",
    # Headers mais comuns
    "contact": "Contact",
    "content-type": "Content-Type",
    "content-length": "Content-Length",
    "authorization": "Authorization",
    "proxy-authorization": "Proxy-Authorization",
    "authentication-info": "Authentication-Info",
    "expires": "Expires",
    "user-agent": "User-Agent",
    "server": "Server",
    "allow": "Allow",
    "supported": "Supported",
    "require": "Require",
    "proxy-require": "Proxy-Require",
    "route": "Route",
    "record-route": "Record-Route",
    "subject": "Subject",
    # Headers de conteúdo
    "content-encoding": "Content-Encoding",
    "content-disposition": "Content-Disposition",
    # Headers de extensões comuns
    "event": "Event",
    "allow-events": "Allow-Events",
    "subscription-state": "Subscription-State",
    "refer-to": "Refer-To",
    "referred-by": "Referred-By",
    "replaces": "Replaces",
    "session-expires": "Session-Expires",
    # Headers P- mais usados (IMS/3GPP)
    "p-asserted-identity": "P-Asserted-Identity",
    "p-preferred-identity": "P-Preferred-Identity",
    "p-charging-vector": "P-Charging-Vector",
    "p-access-network-info": "P-Access-Network-Info",
    "p-called-party-id": "P-Called-Party-ID",
    "p-visited-network-id": "P-Visited-Network-ID",
    "p-associated-uri": "P-Associated-URI",
    "p-served-user": "P-Served-User",
    "p-dcs-trace-party-id": "P-DCS-Trace-Party-ID",
    "p-dcs-osps": "P-DCS-OSPS",
    "p-dcs-billing-info": "P-DCS-Billing-Info",
    "p-dcs-laes": "P-DCS-LAES",
    "p-dcs-redirect": "P-DCS-Redirect",
    # Headers de qualidade/prioridade
    "priority": "Priority",
    "accept": "Accept",
    "accept-encoding": "Accept-Encoding",
    "accept-language": "Accept-Language",
    "accept-contact": "Accept-Contact",
    "reject-contact": "Reject-Contact",
    "request-disposition": "Request-Disposition",
    # Headers informativos
    "date": "Date",
    "timestamp": "Timestamp",
    "retry-after": "Retry-After",
    "warning": "Warning",
    "unsupported": "Unsupported",
    "identity": "Identity",
    "privacy": "Privacy",
    "origination-id": "Origination-ID",
}

# Standard SIP response reason phrases (RFC 3261)
REASON_PHRASES = {
    100: "Trying",
    180: "Ringing",
    181: "Call Is Being Forwarded",
    182: "Queued",
    183: "Session Progress",
    200: "OK",
    202: "Accepted",
    300: "Multiple Choices",
    301: "Moved Permanently",
    302: "Moved Temporarily",
    305: "Use Proxy",
    380: "Alternative Service",
    400: "Bad Request",
    401: "Unauthorized",
    402: "Payment Required",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    406: "Not Acceptable",
    407: "Proxy Authentication Required",
    408: "Request Timeout",
    410: "Gone",
    413: "Request Entity Too Large",
    414: "Request-URI Too Long",
    415: "Unsupported Media Type",
    416: "Unsupported URI Scheme",
    420: "Bad Extension",
    421: "Extension Required",
    423: "Interval Too Brief",
    480: "Temporarily Unavailable",
    481: "Call/Transaction Does Not Exist",
    482: "Loop Detected",
    483: "Too Many Hops",
    484: "Address Incomplete",
    485: "Ambiguous",
    486: "Busy Here",
    487: "Request Terminated",
    488: "Not Acceptable Here",
    491: "Request Pending",
    493: "Undecipherable",
    500: "Internal Server Error",
    501: "Not Implemented",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Server Time-out",
    505: "Version Not Supported",
    513: "Message Too Large",
    600: "Busy Everywhere",
    603: "Decline",
    604: "Does Not Exist Anywhere",
    606: "Not Acceptable",
}
