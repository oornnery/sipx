"""FastAPI REST wrapper around sipx AsyncClient."""

from sipx_fastapi.app import app, create_app

__all__ = ["app", "create_app"]
