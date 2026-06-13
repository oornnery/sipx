"""Console entrypoint for the sipx FastAPI service."""

from __future__ import annotations

import uvicorn

from sipx_fastapi.config import load_settings


def main() -> None:
    settings = load_settings()
    uvicorn.run(
        "sipx_fastapi.app:app",
        host=settings.host,
        port=settings.port,
        factory=False,
    )


if __name__ == "__main__":
    main()
