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

## In-Dialog Call With DTMF

```bash
uv run --package sipx-cli sipx call sip:ivr@example.com --aor sip:1001@example.com --registrar sip:pbx.example.com --codec PCMU --audio noise --rtp-stats --dtmf '123#' --duration 3 --debug-sip
```

`--dtmf` sends each digit with SIP INFO `application/dtmf-relay` after the call is confirmed. Repeat `--dtmf` for multiple groups.

## Raw INFO DTMF Probe

```bash
uv run --package sipx-cli sipx request INFO sip:ivr@example.com --from sip:1001@example.com -H 'Content-Type: application/dtmf-relay' -d $'Signal=1\r\nDuration=160\r\n' --include --debug-sip
```

This is useful for endpoint probing. Prefer `sipx call --dtmf` when DTMF must be sent inside a confirmed dialog.

## Listen And Answer

```bash
uv run --package sipx-cli sipx listen --aor sip:1001@example.com --registrar sip:pbx.example.com --local-port 5062 --audio silence --duration 30 --debug-sip
```

## Public Mizu Demo

```bash
uv run --package sipx-scenarios python apps/scenarios/examples/mizu/register.py --local-host <your-local-ip> --keepalive 5
uv run --package sipx-scenarios python apps/scenarios/examples/mizu/options.py --local-host <your-local-ip>
uv run --package sipx-scenarios python apps/scenarios/examples/mizu/invite_without_sdp.py sip:<target>@demo.mizu-voip.com:37075 --local-host <your-local-ip>
uv run --package sipx-scenarios python apps/scenarios/examples/mizu/invite_with_sdp.py sip:<target>@demo.mizu-voip.com:37075 --local-host <your-local-ip> --audio noise --duration 3
uv run --package sipx-scenarios python apps/scenarios/examples/mizu/metrics.py sip:<target>@demo.mizu-voip.com:37075 --local-host <your-local-ip> --audio noise
```

The public demo account is intentionally public. Private provider accounts must stay in environment variables or local, untracked config.

The older compact Mizu helper is still runnable as a Python file:

```bash
uv run --package sipx-scenarios python apps/scenarios/examples/sip/mizu_call.py register --local-host <your-local-ip>
uv run --package sipx-scenarios python apps/scenarios/examples/sip/mizu_call.py call sip:<target>@demo.mizu-voip.com:37075 --local-host <your-local-ip> --digits '123#'
```

## Python Call With DTMF

```bash
SIPX_AOR=sip:1001@example.com \
SIPX_REGISTRAR=sip:pbx.example.com \
SIPX_USERNAME=1001 \
SIPX_PASSWORD=... \
uv run --package sipx-scenarios python apps/scenarios/examples/sip/call_with_dtmf.py sip:ivr@example.com --digits '123#'
```
