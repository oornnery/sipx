# sipx

Modern, asyncio-driven SIP utilities with a Rich-powered CLI demo.

## Features

- Async SIP client covering REGISTER, OPTIONS, INVITE, MESSAGE, and BYE flows
- Digest authentication with automatic retries for REGISTER, MESSAGE, and INVITE
- Rich console UI with progress indicators, summary panels, and raw-response panels
- Transport layer supporting UDP and TCP with multi-response handling and keep-alive awareness

## Requirements

- Python 3.12 or newer
- [uv](https://github.com/astral-sh/uv) for dependency management and project tasks

## Getting Started

Install dependencies and run the demo against the public Mizu SIP playground:

```bash
uv sync
uv run python -m sipx.demo --wait 2
```

Command-line options include skip flags for each transaction (`--skip-register`, `--skip-options`, `--skip-invite`, `--skip-message`) and `--debug` for verbose logging and raw SIP panels. Default credentials target the hosted demo server.

## Development

Run linting and tests before committing:

```bash
uv run ruff check sipx
uv run pytest
```

Build distributables (wheel and sdist):

```bash
uv build
```

## License

This project is released under the MIT License. See `LICENSE` for details.
