from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ProfileAccount:
    aor: str = ""
    registrar: str = ""
    username: str | None = None
    password: str | None = None
    contact_user: str | None = None
    remote_host: str = "127.0.0.1"
    remote_port: int = 5060

    @property
    def remote(self) -> tuple[str, int]:
        return self.remote_host, self.remote_port


@dataclass(frozen=True, slots=True)
class SipOverrides:
    headers: dict[str, str] = field(default_factory=dict)
    sdp_body: str | None = None
    retransmission_intervals: tuple[float, ...] = ()
    allow_malformed: bool = False


@dataclass(frozen=True, slots=True)
class MediaOverrides:
    codecs: tuple[str, ...] = ("PCMU", "PCMA")
    dtmf: str = "rfc4733"
    sample_rate: int = 8000


@dataclass(frozen=True, slots=True)
class Profile:
    name: str
    mode: str = "strict"
    runtime: str = "sip"
    account: ProfileAccount = field(default_factory=ProfileAccount)
    sip: SipOverrides = field(default_factory=SipOverrides)
    media: MediaOverrides = field(default_factory=MediaOverrides)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("profile name is required")
        if self.mode not in {"strict", "lab"}:
            raise ValueError("profile mode must be strict or lab")
        if self.mode == "strict" and (
            self.sip.allow_malformed or self.sip.sdp_body is not None
        ):
            raise ValueError("strict profiles cannot enable lab SIP overrides")
        if self.account.remote_port <= 0 or self.account.remote_port > 65535:
            raise ValueError("remote_port must be between 1 and 65535")

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> Profile:
        return cls(
            name=name,
            mode=str(data.get("mode", "strict")),
            runtime=str(data.get("runtime", "sip")),
            account=ProfileAccount(**dict(data.get("account") or {})),
            sip=_sip_from_dict(dict(data.get("sip") or {})),
            media=_media_from_dict(dict(data.get("media") or {})),
        )


def load_profiles(path: str | Path = "harness.toml") -> dict[str, Profile]:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    profiles = data.get("profiles") or {}
    if not isinstance(profiles, dict):
        raise ValueError("profiles must be a table")
    return {
        name: Profile.from_dict(name, dict(value)) for name, value in profiles.items()
    }


def _media_from_dict(data: dict[str, Any]) -> MediaOverrides:
    if "codecs" in data:
        data["codecs"] = tuple(str(codec) for codec in data["codecs"])
    return MediaOverrides(**data)


def _sip_from_dict(data: dict[str, Any]) -> SipOverrides:
    if "headers" in data:
        data["headers"] = {
            str(key): str(value) for key, value in data["headers"].items()
        }
    if "retransmission_intervals" in data:
        data["retransmission_intervals"] = tuple(
            float(interval) for interval in data["retransmission_intervals"]
        )
    return SipOverrides(**data)
