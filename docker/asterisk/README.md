# Asterisk Lab

Local Asterisk 22 lab for `sipx` integration tests.

## Start

```bash
docker compose -f docker/asterisk/docker-compose.yml up --build
```

The lab exposes:

- ARI: `http://127.0.0.1:8088/ari`
- SIP UDP: `127.0.0.1:5060`
- RTP UDP: `10000-10020`

Default lab-only ARI credentials are `sipx:sipx`.

## Run Opt-In Tests

```bash
SIPX_ASTERISK_INTEGRATION=1 python -m pytest apps/asterisk/tests/test_asterisk_integration.py
```

The default test suite does not require Docker or a running Asterisk instance.

## Native SIP UAS Targets

- `sip:1000@127.0.0.1:5060`: answers and hangs up immediately.
- `sip:1001@127.0.0.1:5060`: answers and waits long enough for the native caller to hang up.

## ARI/Stasis Target

- `PJSIP/1000`: routes into `Stasis(sipx,inbound)` for ARI backend experiments.
