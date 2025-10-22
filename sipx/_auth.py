from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(slots=True)
class DigestCredentials:
    username: str
    password: str
    realm: Optional[str] = None


def _md5_hex(value: str) -> str:
    return hashlib.md5(value.encode()).hexdigest()


def parse_challenge(header_value: str) -> Dict[str, str]:
    value = header_value.strip()
    if value.lower().startswith("digest "):
        value = value[7:]
    params: Dict[str, str] = {}
    for part in value.split(","):
        if "=" not in part:
            continue
        key, val = part.split("=", 1)
        params[key.strip().lower()] = val.strip().strip('"')
    return params


def build_authorization_header(
    method: str,
    uri: str,
    challenge: Dict[str, str],
    credentials: DigestCredentials,
    *,
    nonce_count: int = 1,
    algorithm: str = "MD5",
    qop: str = "auth",
) -> str:
    realm = challenge.get("realm", credentials.realm or "")
    nonce = challenge.get("nonce", "")
    opaque = challenge.get("opaque")

    nc_value = f"{nonce_count:08x}"
    cnonce = os.urandom(8).hex()
    ha1 = _md5_hex(f"{credentials.username}:{realm}:{credentials.password}")
    ha2 = _md5_hex(f"{method}:{uri}")

    if qop:
        response = _md5_hex(f"{ha1}:{nonce}:{nc_value}:{cnonce}:{qop}:{ha2}")
    else:
        response = _md5_hex(f"{ha1}:{nonce}:{ha2}")

    parts = [
        f'username="{credentials.username}"',
        f'realm="{realm}"',
        f'nonce="{nonce}"',
        f'uri="{uri}"',
        f'response="{response}"',
        f"algorithm={algorithm}",
    ]
    if opaque:
        parts.append(f'opaque="{opaque}"')
    if qop:
        parts.extend([f"qop={qop}", f"nc={nc_value}", f'cnonce="{cnonce}"'])

    return "Digest " + ", ".join(parts)


__all__ = ["DigestCredentials", "build_authorization_header", "parse_challenge"]
