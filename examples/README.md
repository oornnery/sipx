# sipx - Examples

Full demo exercising all components of the sipx library.

## Run

```bash
# Start Asterisk
cd docker/asterisk && docker-compose up -d

# Run demo
uv run python examples/asterisk_demo.py
```

## What is tested

- Constants, Headers, MessageParser, SDPBody, Auth, FSM (offline)
- SIPServer with custom handlers
- 3 Asterisk users (OPTIONS, REGISTER, INVITE, ACK, BYE, MESSAGE, INFO)
- Auth: invalid creds, per-request override, auto re-registration
- SDP: early offer, late offer, create_answer, codec analysis
- Events: on_request, on_response, @event_handler with method/status/tuple

See [docs/SDD.md](../docs/SDD.md) for the full spec.
