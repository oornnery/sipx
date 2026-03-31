"""
SIP Routing — Route and Record-Route header processing (RFC 3261 Section 16).

Handles:
  - Record-Route: proxies add themselves to the route set
  - Route: subsequent requests follow the recorded route
  - Loose routing (;lr) vs strict routing

Usage::

    route_set = RouteSet.from_response(response)
    route_set.apply(request)  # adds Route headers to next request
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._models._message import Request, Response


@dataclass
class RouteSet:
    """Ordered set of Route URIs for a SIP dialog.

    Built from Record-Route headers in responses, then applied
    as Route headers in subsequent requests.
    """

    routes: list[str] = field(default_factory=list)

    @classmethod
    def from_response(cls, response: Response) -> RouteSet:
        """Extract route set from Record-Route headers in a response.

        Per RFC 3261 Section 12.1.2: the route set is built from
        Record-Route headers in reverse order for UAC.
        """
        rr = response.headers.get("Record-Route")
        if not rr:
            return cls()

        # Parse comma-separated or multiple Record-Route values
        routes = []
        for part in rr.split(","):
            uri = part.strip().strip("<>").strip()
            if uri:
                routes.append(uri)

        # UAC reverses the Record-Route order
        routes.reverse()
        return cls(routes=routes)

    @classmethod
    def from_request(cls, request: Request) -> RouteSet:
        """Extract route set from Route headers in a request."""
        route = request.headers.get("Route")
        if not route:
            return cls()

        routes = []
        for part in route.split(","):
            uri = part.strip().strip("<>").strip()
            if uri:
                routes.append(uri)

        return cls(routes=routes)

    def apply(self, request: Request) -> None:
        """Add Route headers to a request based on the route set.

        Per RFC 3261 Section 12.2.1.1:
        - If route set is not empty, add Route headers
        - If first route has ;lr (loose routing), keep Request-URI as-is
        - If first route is strict (no ;lr), set Request-URI to first route
        """
        if not self.routes:
            return

        # Check if first route uses loose routing
        first = self.routes[0]
        is_loose = ";lr" in first.lower()

        if is_loose:
            # Loose routing: all routes as Route headers, URI unchanged
            route_value = ", ".join(f"<{r}>" for r in self.routes)
            request.headers["Route"] = route_value
        else:
            # Strict routing: first route becomes Request-URI,
            # remaining routes + original URI as Route headers
            original_uri = request.uri
            request.uri = first

            remaining = self.routes[1:] + [original_uri]
            if remaining:
                route_value = ", ".join(f"<{r}>" for r in remaining)
                request.headers["Route"] = route_value

    @property
    def is_empty(self) -> bool:
        return len(self.routes) == 0

    @property
    def is_loose(self) -> bool:
        """Check if first route uses loose routing (;lr)."""
        if not self.routes:
            return False
        return ";lr" in self.routes[0].lower()

    def __len__(self) -> int:
        return len(self.routes)

    def __repr__(self) -> str:
        return f"RouteSet({self.routes})"


__all__ = ["RouteSet"]
