"""Client-side REGISTER flow with Digest authentication.

Drives REGISTER, refresh, and unregister requests, consumes 401/407
challenges, and builds the authenticated retry while tracking registration
state.

References:
    RFC 3261 §10 - Registrations
    RFC 3261 §10.2 - Constructing the REGISTER Request
    RFC 3261 §22 - Usage of HTTP Authentication
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sipx.sip.auth import (
    DigestChallenge,
    build_digest_authorization,
    parse_digest_challenge,
)
from sipx.sip.message import SipRequest, SipResponse
from sipx.sip.requests import create_register_request
from sipx.sip.uri import SipUri


class RegisterClientError(ValueError):
    pass


class RegisterClientState(StrEnum):
    READY = "ready"
    CHALLENGED = "challenged"
    REGISTERED = "registered"
    UNREGISTERED = "unregistered"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RegisterChallenge:
    challenge: DigestChallenge
    authorization_header: str


class RegisterClientFlow:
    def __init__(
        self,
        *,
        registrar: SipUri,
        aor: SipUri,
        contact: SipUri,
        call_id: str,
        from_tag: str,
        expires: int = 3600,
    ) -> None:
        if expires < 0:
            raise RegisterClientError("REGISTER expires must be non-negative")
        self.registrar = registrar
        self.aor = aor
        self.contact = contact
        self.call_id = call_id
        self.from_tag = from_tag
        self.default_expires = expires
        self.cseq = 0
        self.state = RegisterClientState.READY
        self.challenge: RegisterChallenge | None = None
        self.last_response: SipResponse | None = None
        self._last_expires = expires

    def create_register(
        self,
        *,
        branch: str,
        expires: int | None = None,
    ) -> SipRequest:
        requested_expires = self.default_expires if expires is None else expires
        if requested_expires < 0:
            raise RegisterClientError("REGISTER expires must be non-negative")
        self.cseq += 1
        self._last_expires = requested_expires
        return create_register_request(
            registrar=self.registrar,
            aor=self.aor,
            contact=self.contact,
            call_id=self.call_id,
            branch=branch,
            from_tag=self.from_tag,
            cseq=self.cseq,
            expires=requested_expires,
        )

    def create_authenticated_register(
        self,
        *,
        branch: str,
        username: str,
        password: str,
        cnonce: str,
        nonce_count: str = "00000001",
        expires: int | None = None,
    ) -> SipRequest:
        if self.challenge is None:
            raise RegisterClientError("Digest challenge is required before auth retry")
        request = self.create_register(branch=branch, expires=expires)
        request.headers.add(
            self.challenge.authorization_header,
            build_digest_authorization(
                username=username,
                password=password,
                method="REGISTER",
                uri=str(self.registrar),
                challenge=self.challenge.challenge,
                cnonce=cnonce,
                nonce_count=nonce_count,
            ),
        )
        return request

    def create_unregister(self, *, branch: str) -> SipRequest:
        return self.create_register(branch=branch, expires=0)

    def receive_response(self, response: SipResponse) -> RegisterClientState:
        self.last_response = response
        if 100 <= response.status_code < 200:
            return self.state
        if response.status_code == 401:
            self.challenge = _extract_challenge(
                response,
                challenge_header="WWW-Authenticate",
                authorization_header="Authorization",
            )
            self.state = RegisterClientState.CHALLENGED
        elif response.status_code == 407:
            self.challenge = _extract_challenge(
                response,
                challenge_header="Proxy-Authenticate",
                authorization_header="Proxy-Authorization",
            )
            self.state = RegisterClientState.CHALLENGED
        elif 200 <= response.status_code < 300:
            self.state = (
                RegisterClientState.UNREGISTERED
                if self._last_expires == 0
                else RegisterClientState.REGISTERED
            )
        elif 300 <= response.status_code < 700:
            self.state = RegisterClientState.FAILED
        else:
            raise RegisterClientError(
                f"invalid SIP response code: {response.status_code}"
            )
        return self.state


def _extract_challenge(
    response: SipResponse,
    *,
    challenge_header: str,
    authorization_header: str,
) -> RegisterChallenge:
    value = response.headers.get(challenge_header)
    if value is None:
        raise RegisterClientError(f"{challenge_header} header is required")
    return RegisterChallenge(
        challenge=parse_digest_challenge(value),
        authorization_header=authorization_header,
    )
