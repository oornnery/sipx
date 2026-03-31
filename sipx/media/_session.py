"""
High-level call session helper.

Wraps a SIP dialog (client + response) together with RTP and DTMF
into a single convenience object with a context-manager interface.

Example::

    r = client.invite("sip:100@pbx.com", body=sdp)
    with CallSession(client, r, rtp_port=8000) as call:
        call.play_tone(440, 500)
        digits = call.collect_dtmf(max_digits=4, timeout=10)
        call.hangup()
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sipx._client import Client
    from sipx.models._message import Response

    from ._rtp import RTPSession


# ============================================================================
# DTMF Helper
# ============================================================================


class DTMFHelper:
    """Wraps ``DTMFSender`` + ``DTMFCollector`` for convenience.

    Lazily creates sender/collector on first use so the RTP session
    only needs to be running when DTMF is actually used.

    Args:
        rtp_session: An active ``RTPSession`` instance.
    """

    def __init__(self, rtp_session: RTPSession) -> None:
        self._rtp = rtp_session
        self._sender: Any = None

    def send(self, digits: str, duration_ms: int = 160) -> None:
        """Send one or more DTMF digits via RFC 4733.

        Args:
            digits: String of digits to send (e.g. ``"123#"``).
            duration_ms: Per-digit tone duration in milliseconds.
        """
        if self._sender is None:
            from ._dtmf import DTMFSender

            self._sender = DTMFSender(self._rtp)

        for d in digits:
            self._sender.send_digit(d, duration_ms=duration_ms)
            time.sleep(0.05)  # inter-digit gap

    def collect(self, max_digits: int = 1, timeout: float = 10.0) -> str:
        """Collect DTMF digits from the remote party.

        Args:
            max_digits: Maximum digits to collect.
                Use ``0`` for unlimited (collect until timeout).
            timeout: Collection timeout in seconds.

        Returns:
            String of collected digits.
        """
        from ._dtmf import DTMFCollector

        effective_max = max_digits if max_digits > 0 else 9999
        collector = DTMFCollector(self._rtp, max_digits=effective_max, timeout=timeout)
        return collector.collect()


# ============================================================================
# Call Session
# ============================================================================


class CallSession:
    """High-level call session that bundles SIP dialog, RTP, and DTMF.

    Automatically sets up an ``RTPSession`` from the response SDP and
    provides convenience methods for media playback, recording, and
    DTMF interaction.

    Args:
        client: The ``Client`` that initiated the call.
        response: The SIP response (typically 200 OK with SDP).
        rtp_port: Local UDP port for RTP media.
    """

    def __init__(self, client: Client, response: Response, rtp_port: int) -> None:
        self._client = client
        self._response = response
        self._rtp_port = rtp_port
        self._rtp: RTPSession | None = None
        self._dtmf: DTMFHelper | None = None
        self._setup_rtp()

    def _setup_rtp(self) -> None:
        """Create an RTPSession from the response SDP if available."""
        body = self._response.body
        if body and hasattr(body, "get_rtp_params"):
            from ._rtp import RTPSession

            self._rtp = RTPSession.from_sdp(
                body, self._client.local_address.host, self._rtp_port
            )

    @property
    def rtp(self) -> RTPSession | None:
        """The underlying ``RTPSession``, or ``None`` if SDP was absent."""
        return self._rtp

    @property
    def dtmf(self) -> DTMFHelper | None:
        """Lazily-created ``DTMFHelper``, or ``None`` if no RTP session."""
        if self._dtmf is None and self._rtp is not None:
            self._dtmf = DTMFHelper(self._rtp)
        return self._dtmf

    # ------------------------------------------------------------------
    # Media helpers
    # ------------------------------------------------------------------

    def play(self, audio: bytes) -> None:
        """Send raw PCM audio over RTP.

        Args:
            audio: 16-bit signed little-endian PCM bytes.
        """
        if self._rtp is not None:
            self._rtp.send_audio(audio)

    def play_tone(self, freq: int = 440, duration_ms: int = 500) -> None:
        """Generate and play a sine-wave tone.

        Args:
            freq: Tone frequency in Hz.
            duration_ms: Tone duration in milliseconds.
        """
        from ._generators import ToneGenerator

        self.play(ToneGenerator(freq).generate(duration_ms))

    def send_dtmf(self, digits: str, duration_ms: int = 160) -> None:
        """Send DTMF digits via RFC 4733.

        Args:
            digits: Digits to send (e.g. ``"123#"``).
            duration_ms: Per-digit tone duration in milliseconds.
        """
        if self.dtmf is not None:
            self.dtmf.send(digits, duration_ms)

    def collect_dtmf(self, max_digits: int = 1, timeout: float = 10.0) -> str:
        """Collect DTMF digits from the remote party.

        Args:
            max_digits: Maximum digits to collect (``0`` = unlimited).
            timeout: Timeout in seconds.

        Returns:
            String of collected digits (may be empty on timeout).
        """
        if self.dtmf is not None:
            return self.dtmf.collect(max_digits, timeout)
        return ""

    def record(self, duration: float) -> bytes:
        """Record incoming audio for a given duration.

        Args:
            duration: Recording duration in seconds.

        Returns:
            Concatenated raw PCM bytes received.
        """
        if self._rtp is None:
            return b""

        chunks: list[bytes] = []
        deadline = time.time() + duration
        while time.time() < deadline:
            audio = self._rtp.recv_audio(timeout=0.5)
            if audio:
                chunks.append(audio)
        return b"".join(chunks)

    # ------------------------------------------------------------------
    # Signaling
    # ------------------------------------------------------------------

    def hangup(self) -> None:
        """Send a BYE to terminate the call."""
        self._client.bye(response=self._response)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> CallSession:
        if self._rtp is not None:
            self._rtp.start()
        return self

    def __exit__(self, *_: object) -> None:
        if self._rtp is not None:
            self._rtp.stop()


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "DTMFHelper",
    "CallSession",
]
