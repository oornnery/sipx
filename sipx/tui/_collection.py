"""Collection manager — saved SIP profiles, roles, and flows (YAML)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml  # noqa: F401

    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

_log = logging.getLogger("sipx.tui.collection")

# Default base directory for collections
DEFAULT_COLLECTION_DIR = Path.home() / ".config" / "sipx" / "collection"

CATEGORIES = ("uac", "flows")


@dataclass
class SipProfile:
    """A single saved SIP profile/role."""

    name: str
    category: str  # uac, uas, b2bua, flows, profiles
    uri: str = ""
    method: str = "INVITE"
    transport: str = "UDP"
    auth_user: str = ""
    auth_pass: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
    path: str = ""  # file path if loaded from disk

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict (for YAML)."""
        d: dict[str, Any] = {
            "name": self.name,
            "role": self.category,
            "uri": self.uri,
            "method": self.method,
            "transport": self.transport,
        }
        if self.auth_user:
            d["auth"] = {"username": self.auth_user, "password": self.auth_pass}
        if self.headers:
            d["headers"] = self.headers
        if self.body:
            d["body"] = self.body
        if self.extra:
            d.update(self.extra)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: str = "") -> SipProfile:
        """Deserialize from dict."""
        auth = data.get("auth", {})
        return cls(
            name=data.get("name", "unnamed"),
            category=data.get("role", "uac"),
            uri=data.get("uri", ""),
            method=data.get("method", "INVITE"),
            transport=data.get("transport", "UDP"),
            auth_user=auth.get("username", "") if isinstance(auth, dict) else "",
            auth_pass=auth.get("password", "") if isinstance(auth, dict) else "",
            headers=data.get("headers", {}),
            body=data.get("body", ""),
            extra={
                k: v
                for k, v in data.items()
                if k
                not in (
                    "name",
                    "role",
                    "uri",
                    "method",
                    "transport",
                    "auth",
                    "headers",
                    "body",
                )
            },
            path=path,
        )


class CollectionManager:
    """Manages the on-disk collection of SIP profiles and flows."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or DEFAULT_COLLECTION_DIR

    def ensure_dirs(self) -> None:
        """Create the collection directory structure."""
        for cat in CATEGORIES:
            (self.base_dir / cat).mkdir(parents=True, exist_ok=True)

    def list_items(self) -> dict[str, list[dict[str, str]]]:
        """List all collection items grouped by category.

        Returns dict like: {"uac": [{"name": "basic-call", "path": "..."}]}
        """
        result: dict[str, list[dict[str, str]]] = {}
        for cat in CATEGORIES:
            cat_dir = self.base_dir / cat
            entries: list[dict[str, str]] = []
            if cat_dir.exists():
                for fp in sorted(cat_dir.glob("*.yaml")):
                    entries.append({"name": fp.stem, "path": str(fp)})
                for fp in sorted(cat_dir.glob("*.yml")):
                    entries.append({"name": fp.stem, "path": str(fp)})
            result[cat] = entries
        return result

    def load_profile(self, path: str) -> SipProfile | None:
        """Load a profile from a YAML file."""
        if not _HAS_YAML:
            _log.warning("PyYAML not installed; cannot load profiles")
            return None
        fp = Path(path)
        if not fp.exists():
            return None
        try:
            data = yaml.safe_load(fp.read_text())
            if not isinstance(data, dict):
                return None
            return SipProfile.from_dict(data, path=str(fp))
        except Exception:
            _log.exception("Failed to load profile %s", path)
            return None

    def save_profile(self, profile: SipProfile) -> str:
        """Save a profile to YAML. Returns the file path."""
        self.ensure_dirs()
        slug = profile.name.lower().replace(" ", "-")
        fp = self.base_dir / profile.category / f"{slug}.yaml"

        if _HAS_YAML:
            fp.write_text(yaml.dump(profile.to_dict(), default_flow_style=False))
        else:
            # Fallback: write simple YAML manually
            lines = [f"name: {profile.name}", f"role: {profile.category}"]
            if profile.uri:
                lines.append(f"uri: {profile.uri}")
            if profile.method:
                lines.append(f"method: {profile.method}")
            lines.append(f"transport: {profile.transport}")
            if profile.auth_user:
                lines.append("auth:")
                lines.append(f"  username: {profile.auth_user}")
                lines.append(f"  password: {profile.auth_pass}")
            if profile.headers:
                lines.append("headers:")
                for k, v in profile.headers.items():
                    lines.append(f"  {k}: {v}")
            fp.write_text("\n".join(lines) + "\n")

        profile.path = str(fp)
        return str(fp)

    def delete_profile(self, path: str) -> bool:
        """Delete a profile file."""
        fp = Path(path)
        if fp.exists():
            fp.unlink()
            return True
        return False

    def load_flow_yaml(self, path: str) -> str:
        """Load raw flow YAML text."""
        fp = Path(path)
        if fp.exists():
            return fp.read_text()
        return ""
