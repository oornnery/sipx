# SIP Examples

These examples use explicit CLI flags, environment variables, or public demo settings. Do not put private SIP or LLM credentials in files.

Run commands from the repository root. Use `uv run` so local workspace packages are importable.

## Print The CLI Flow

```bash
uv run --package sipx-scenarios python apps/scenarios/examples/sip/sip_cli_flow.py
```

## Register

```bash
uv run --package sipx-cli sipx register --aor sip:1001@example.com --registrar sip:pbx.example.com --username 1001 --password "$SIP_PASSWORD" --debug-sip --keepalive 10
```

## OPTIONS Probe

```bash
uv run --package sipx-cli sipx options sip:pbx.example.com --from sip:1001@example.com --include --debug-sip
```

## MESSAGE

```bash
uv run --package sipx-cli sipx message sip:1002@example.com 'hello from sipx' --from sip:1001@example.com --debug-sip
```

## Raw INFO DTMF Probe

```bash
uv run --package sipx-cli sipx request INFO sip:ivr@example.com --from sip:1001@example.com -H 'Content-Type: application/dtmf-relay' -d $'Signal=1\r\nDuration=160\r\n' --include --debug-sip
```

## Python AsyncClient Examples

The root `sipx/examples/` directory has env-driven `AsyncClient` examples for REGISTER, INVITE, MESSAGE, and SUBSCRIBE:

```bash
uv run python -m sipx.examples.register
SIPX_TARGET=sip:echo@example.com uv run python -m sipx.examples.invite
```
