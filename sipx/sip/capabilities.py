"""UA capability headers (Allow, Accept, Supported, Allow-Events).

``SipCapabilities`` renders a UA's supported methods, body types, extensions,
and event packages as the corresponding SIP headers on an outgoing message.

References:
    RFC 3261 §20.5 - Allow
    RFC 3261 §20.1 - Accept
    RFC 3261 §20.37 - Supported
    RFC 6665 §8.2.2 - Allow-Events (SIP-Specific Event Notification)
"""

from __future__ import annotations

from dataclasses import dataclass

from sipx.sip.headers import HeaderMap


@dataclass(frozen=True, slots=True)
class SipCapabilities:
    accept: tuple[str, ...] = ()
    allow: tuple[str, ...] = ()
    allow_events: tuple[str, ...] = ()
    supported: tuple[str, ...] = ()

    def apply(self, headers: HeaderMap) -> None:
        _set_csv(headers, "Accept", self.accept)
        _set_csv(headers, "Allow", self.allow)
        _set_csv(headers, "Allow-Events", self.allow_events)
        _set_csv(headers, "Supported", self.supported)


def _set_csv(headers: HeaderMap, name: str, values: tuple[str, ...]) -> None:
    if values:
        headers.set(name, ", ".join(values))
