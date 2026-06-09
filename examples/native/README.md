# Native SIP Examples

These examples use environment variables or public demo profiles. Do not put private SIP or LLM credentials in files.

Run commands from the repository root. Use `uv run` so the local `sipx` package is importable.

## Print The CLI Flow

```bash
uv run python examples/native/sip_cli_flow.py
```

## Register

```bash
sipx register lab --config harness.toml --debug-sip --keepalive 10
```

## OPTIONS Probe

```bash
sipx options sip:pbx.example.com --from sip:1001@example.com --include --debug-sip
```

## MESSAGE

```bash
sipx message sip:1002@example.com 'hello from sipx' --from sip:1001@example.com --debug-sip
```

## In-Dialog Call With DTMF

```bash
sipx call sip:ivr@example.com --profile lab --config harness.toml --codec PCMU --dtmf '123#' --duration 3 --debug-sip
```

`--dtmf` sends each digit with SIP INFO `application/dtmf-relay` after the call is confirmed. Repeat `--dtmf` for multiple groups.

## Raw INFO DTMF Probe

```bash
sipx request INFO sip:ivr@example.com --from sip:1001@example.com -H 'Content-Type: application/dtmf-relay' -d $'Signal=1\r\nDuration=160\r\n' --include --debug-sip
```

This is useful for endpoint probing. Prefer `sipx call --dtmf` when the DTMF must be sent inside a confirmed dialog.

## Listen And Answer

```bash
sipx listen lab --config harness.toml --duration 30 --debug-sip
```

## Public Mizu Demo

```bash
sipx register mizu_demo --config examples/mizu/harness.toml --local-host <your-local-ip> --keepalive 5 --debug-sip
sipx call sip:<target>@demo.mizu-voip.com:37075 --profile mizu_demo --config examples/mizu/harness.toml --local-host <your-local-ip> --dtmf '123#' --duration 3 --debug-sip
```

The public demo account is intentionally public. Private provider accounts must stay in environment variables or local, untracked config.

The same Mizu flow is runnable as a Python file:

```bash
uv run python examples/native/mizu_call.py register --local-host <your-local-ip>
uv run python examples/native/mizu_call.py call sip:<target>@demo.mizu-voip.com:37075 --local-host <your-local-ip> --digits '123#'
```

## Python Call With DTMF

```bash
SIPX_AOR=sip:1001@example.com \
SIPX_REGISTRAR=sip:pbx.example.com \
SIPX_USERNAME=1001 \
SIPX_PASSWORD=... \
uv run python examples/native/call_with_dtmf.py sip:ivr@example.com --digits '123#'
```
