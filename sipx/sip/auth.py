"""HTTP Digest authentication for SIP (MD5).

Parses ``WWW-Authenticate``/``Proxy-Authenticate`` Digest challenges and
builds the matching ``Authorization``/``Proxy-Authorization`` header, with
optional ``qop=auth``. Only the MD5 algorithm is supported.

References:
    RFC 3261 §22 - Usage of HTTP Authentication
    RFC 3261 §22.4 - The Digest Authentication Scheme
    RFC 2617 - HTTP Authentication: Basic and Digest Access Authentication
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sipx.sip.message import SipResponse


class SipAuthError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DigestChallenge:
    realm: str
    nonce: str
    algorithm: str = "MD5"
    qop: str | None = None
    opaque: str | None = None


def parse_digest_challenge(value: str) -> DigestChallenge:
    text = value.strip()
    if text.lower().startswith("digest "):
        text = text[7:].strip()
    fields = _parse_digest_fields(text)
    try:
        realm = fields["realm"]
        nonce = fields["nonce"]
    except KeyError as exc:
        raise SipAuthError("Digest challenge requires realm and nonce") from exc
    return DigestChallenge(
        realm=realm,
        nonce=nonce,
        algorithm=fields.get("algorithm", "MD5"),
        qop=fields.get("qop"),
        opaque=fields.get("opaque"),
    )


def digest_challenge_for_response(response: SipResponse) -> tuple[str, str] | None:
    if response.status_code == 401:
        value = response.headers.get("WWW-Authenticate")
        return ("Authorization", value) if value is not None else None
    if response.status_code == 407:
        value = response.headers.get("Proxy-Authenticate")
        return ("Proxy-Authorization", value) if value is not None else None
    return None


def build_digest_authorization(
    *,
    username: str,
    password: str,
    method: str,
    uri: str,
    challenge: DigestChallenge,
    cnonce: str = "sipx",
    nonce_count: str = "00000001",
    qop: str | None = None,
) -> str:
    if challenge.algorithm.upper() != "MD5":
        raise SipAuthError(f"unsupported Digest algorithm: {challenge.algorithm}")
    selected_qop = qop or _select_qop(challenge.qop)
    ha1 = _md5(f"{username}:{challenge.realm}:{password}")
    ha2 = _md5(f"{method}:{uri}")
    if selected_qop:
        response = _md5(
            f"{ha1}:{challenge.nonce}:{nonce_count}:{cnonce}:{selected_qop}:{ha2}"
        )
    else:
        response = _md5(f"{ha1}:{challenge.nonce}:{ha2}")

    parts = [
        f'username="{username}"',
        f'realm="{challenge.realm}"',
        f'nonce="{challenge.nonce}"',
        f'uri="{uri}"',
        f'response="{response}"',
        f'algorithm="{challenge.algorithm}"',
    ]
    if challenge.opaque:
        parts.append(f'opaque="{challenge.opaque}"')
    if selected_qop:
        parts.extend(
            [
                f"qop={selected_qop}",
                f"nc={nonce_count}",
                f'cnonce="{cnonce}"',
            ]
        )
    return "Digest " + ", ".join(parts)


def _parse_digest_fields(value: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in _split_quoted_commas(value):
        name, separator, item = part.partition("=")
        if not separator:
            continue
        fields[name.strip().lower()] = item.strip().strip('"')
    return fields


def _split_quoted_commas(value: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    in_quotes = False
    for char in value:
        if char == '"':
            in_quotes = not in_quotes
        if char == "," and not in_quotes:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current).strip())
    return parts


def _select_qop(value: str | None) -> str | None:
    if value is None:
        return None
    options = {item.strip() for item in value.split(",")}
    return "auth" if "auth" in options else None


def _md5(value: str) -> str:
    return hashlib.md5(value.encode("utf-8"), usedforsecurity=False).hexdigest()
