"""sipx TUI — interactive SIP workbench (requires ``pip install sipx[tui]``)."""

from __future__ import annotations

__all__ = ["SipxApp"]


def __getattr__(name: str):
    if name == "SipxApp":
        from ._app import SipxApp

        return SipxApp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
