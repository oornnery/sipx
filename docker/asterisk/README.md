# Asterisk Docker for SIPX Testing

Docker container with Asterisk configured to test the SIPX library with 3 different authentication policies.

**Version**: 0.3.0
**Asterisk**: 18+
**Status**: Production

## How to Use

### 1. Build and Start

```bash
cd docker/asterisk
docker-compose up -d --build
```

### 2. Check Logs

```bash
docker-compose logs -f
```

### 3. Connect to Asterisk CLI

```bash
docker exec -it sipx-asterisk asterisk -rvvv
```

### 4. Check Registration

In the Asterisk CLI:
```
pjsip show endpoints
pjsip show registrations
pjsip show contacts
```

## Configured Users

### Authentication Policies

This setup has **3 users with different policies** to test various authentication scenarios:

| Username | Password | Policy | Client Port | Context |
|----------|----------|--------|-------------|---------|
| **1111** | 1111xxx  | **Auth for ALL methods** | 5061 | sipx-test |
| **2222** | 2222xxx  | **OPTIONS without auth, others with auth** | 5062 | sipx-test |
| **3333** | 3333xxx  | **OPTIONS rejected, strict security** | 5063 | sipx-test |

### Policy Details

#### User 1111 - Full Authentication
- Requires authentication for **all** methods (OPTIONS, REGISTER, INVITE)
- Ideal for testing the complete authentication flow
- Used to test `retry_with_auth()` in all scenarios

#### User 2222 - Open OPTIONS (Relaxed)
- **OPTIONS**: Accepted without authentication (for health checks)
- **REGISTER/INVITE**: Requires authentication
- Ideal for testing servers that allow OPTIONS without credentials
- Used to test:
  - INVITE with late offer (SDP answer)
  - Early media detection (183 Session Progress)
  - Codec negotiation

#### User 3333 - Restrictive Security (Paranoid)
- **OPTIONS**: Rejected (403 Forbidden)
- **REGISTER/INVITE**: Requires authentication
- Ideal for testing:
  - Invalid credentials (403)
  - Strict security policies
  - Auto re-registration with threading
  - Rejection handling

## SIPX Client Configuration

### Basic Example

```python
from sipx import Client, Auth

# Credentials
auth = Auth.Digest(username="1111", password="1111xxx")

# Client (use a port other than 5060!)
with Client(local_port=5061, auth=auth) as client:
    response = client.register(aor="sip:1111@127.0.0.1")
    if response.status_code == 401:
        response = client.retry_with_auth(response)
    print(f"Status: {response.status_code}")
```

**Important**:
- Client uses port **5061+** (not 5060)
- Asterisk server uses port **5060**
- Avoids "Address already in use" conflict

## Available Tests

### Echo Test
Dial `100` to test audio (echo)

### Music on Hold
Dial `200` to listen to music

### Voicemail Test
Dial `300` to listen to a voicemail message

### Time Announcement
Dial `400` to hear the time

### Conference Room
Dial `500` to enter a conference room

### Calls Between Extensions
Dial `1111`, `2222`, or `3333` to call other users

## Important Notes

### Ports

- **Asterisk Docker**: Port `5060` (UDP/TCP)
- **SIPX Client**: Use ports `5061`, `5062`, `5063`, etc.
- **Reason**: Avoid "Address already in use" conflict

### Authentication

The SIPX library v0.3.0 uses **explicit manual authentication**:

```python
# Send request
response = client.register(aor="sip:1111@127.0.0.1")

# Check if authentication is needed
if response.status_code == 401:
    # Retry with authentication
    response = client.retry_with_auth(response)
```

**There is no automatic retry** -- you control when and how to authenticate.

## Monitoring

### View active calls
```bash
docker exec sipx-asterisk asterisk -rx "core show channels"
```

### View registered endpoints
```bash
docker exec sipx-asterisk asterisk -rx "pjsip show endpoints"
```

### Debug SIP
```bash
docker exec sipx-asterisk asterisk -rx "pjsip set logger on"
```

### View logs in real time
```bash
docker exec sipx-asterisk tail -f /var/log/asterisk/messages
```

## Stop and Remove

```bash
# Stop containers
docker-compose down

# Stop and remove volumes (clears data)
docker-compose down -v
```

## Troubleshooting

### RTP does not work
- Check if ports 10000-10099/udp are open
- Use `network_mode: host` in docker-compose.yml (already configured)
- On Windows, you may need to use mapped ports instead of host mode

### Authentication fails
- Check username/password in `config/pjsip.conf`
- View logs: `docker-compose logs asterisk`
- Confirm that the client is using the correct credentials

### No audio in calls
- Configure `direct_media=no` in pjsip.conf (already configured)
- Check NAT settings in rtp.conf
- Test with `100` (echo test) to verify RTP flow

### Container does not start
- Check if port 5060 is not in use: `netstat -an | findstr 5060` (Windows)
- View detailed logs: `docker-compose logs asterisk`
- Rebuild the image: `docker-compose build --no-cache`

### Calls drop immediately
- Check dialplan in `config/extensions.conf`
- Confirm that the context is correct (`sipx-test`)
- View Asterisk logs in the CLI: `asterisk -rvvv`

## Useful Asterisk CLI Commands

```bash
# Connect to the CLI
docker exec -it sipx-asterisk asterisk -rvvv

# Inside the CLI:
pjsip show endpoints          # List endpoints
pjsip show registrations      # List active registrations
pjsip show contacts           # List contacts
core show channels            # Show active calls
dialplan show sipx-test       # Show context dialplan
pjsip set logger on           # Enable SIP debug
pjsip set logger off          # Disable SIP debug
core reload                   # Reload configuration
core restart now              # Restart Asterisk

# Exit the CLI: Ctrl+C or 'exit'
```

## Testing with SIPX

### Full Demo (Recommended)

Run the full demo with Rich interface that tests all 3 users:

```bash
uv run examples/asterisk_demo.py
```

**This demo runs 16 tests**:

#### User 1111 (5 tests)
- OPTIONS with authentication
- REGISTER (expires=3600)
- REGISTER update (expires=1800)
- INVITE with create_offer (early offer)
- UNREGISTER

#### User 2222 (5 tests)
- OPTIONS without authentication
- REGISTER
- INVITE with create_answer (late offer)
- Early media detection (183)
- UNREGISTER

#### User 3333 (6 tests)
- OPTIONS (should be rejected -- expected)
- REGISTER with invalid credentials (should fail)
- REGISTER with valid credentials
- INVITE
- Auto re-registration (5s interval)
- UNREGISTER

**Expected result**: 15/16 tests pass (1 intentional failure)

### Example 1: Simple Registration

```python
from sipx import Client, Auth

auth = Auth.Digest(username="1111", password="1111xxx")

with Client(local_port=5061, auth=auth) as client:
    # Register
    response = client.register(aor="sip:1111@127.0.0.1")

    # Handle authentication
    if response.status_code == 401:
        response = client.retry_with_auth(response)

    print(f"Registration: {response.status_code} {response.reason_phrase}")
```

### Example 2: Call to Echo Test

```python
from sipx import Client, Auth, SDPBody
import time

auth = Auth.Digest(username="1111", password="1111xxx")

with Client(local_port=5061, auth=auth) as client:
    # Create SDP offer
    sdp_offer = SDPBody.create_offer(
        session_name="Echo Test",
        origin_username="1111",
        origin_address=client.local_address.host,
        connection_address=client.local_address.host,
        media_specs=[{
            "media": "audio",
            "port": 8000,
            "codecs": [
                {"payload": "0", "name": "PCMU", "rate": "8000"},
                {"payload": "8", "name": "PCMA", "rate": "8000"},
            ]
        }]
    )

    # Call extension 100 (echo test)
    response = client.invite(
        to_uri="sip:100@127.0.0.1",
        from_uri=f"sip:1111@{client.local_address.host}",
        body=sdp_offer.to_string(),
        headers={"Contact": f"<sip:1111@{client.local_address.host}:5061>"}
    )

    # Authentication
    if response.status_code == 401:
        response = client.retry_with_auth(response)

    if response.status_code == 200:
        print(f"INVITE: {response.status_code}")
        client.ack(response=response)
        time.sleep(5)
        client.bye(response=response)
```

### Example 3: Auto Re-Registration

```python
from sipx import Client, Auth
import time

auth = Auth.Digest(username="1111", password="1111xxx")

with Client(local_port=5061, auth=auth) as client:
    # Initial registration
    response = client.register(aor="sip:1111@127.0.0.1")
    if response.status_code == 401:
        response = client.retry_with_auth(response)

    # Enable auto re-registration (threading.Timer)
    client.enable_auto_reregister(
        aor="sip:1111@127.0.0.1",
        interval=300  # Re-register every 5 minutes
    )

    print("Auto re-registration enabled")

    # Keep running (re-registration happens automatically)
    time.sleep(600)  # 10 minutes

    # Disable and remove registration
    client.disable_auto_reregister()
    response = client.unregister(aor="sip:1111@127.0.0.1")
    if response.status_code == 401:
        response = client.retry_with_auth(response)
```

## File Structure

```
asterisk-docker/
├── Dockerfile              # Asterisk Docker image
├── docker-compose.yml      # Container orchestration
├── config/
│   ├── pjsip.conf         # PJSIP configuration (users, transports)
│   ├── extensions.conf    # Dialplan (call routes)
│   ├── rtp.conf           # RTP configuration (audio ports)
│   └── modules.conf       # Loaded modules
└── README.md              # This file
```

## Next Steps

1. **Test Registration**: Run the basic registration script
2. **Test Echo**: Call extension 100 to validate RTP
3. **Test Calls**: Make calls between 1111, 2222, and 3333
4. **Monitor Logs**: Use `pjsip set logger on` for detailed debug
5. **Validate ACK**: Verify ACK sending with sngrep or logs

## Additional Resources

- [Asterisk Official Docs](https://docs.asterisk.org/)
- [PJSIP Configuration](https://wiki.asterisk.org/wiki/display/AST/Configuring+res_pjsip)
- [Dialplan Basics](https://wiki.asterisk.org/wiki/display/AST/Dialplan)
- [RFC 3261 - SIP](https://datatracker.ietf.org/doc/html/rfc3261)

## Advanced Debug

### Capture SIP traffic with tcpdump

```bash
# On the host (not in the container)
sudo tcpdump -i any -s 0 -A 'port 5060'
```

### Use sngrep to visualize SIP flow

```bash
# Install sngrep (Ubuntu/Debian)
sudo apt-get install sngrep

# Run
sudo sngrep port 5060
```

### Detailed Asterisk logs

Edit `config/modules.conf` and add:
```ini
load => logger.so
```

Create `config/logger.conf`:
```ini
[general]
dateformat=%F %T

[logfiles]
console => notice,warning,error,debug,verbose
messages => notice,warning,error,verbose
full => notice,warning,error,debug,verbose
```

## Related Documentation

- **[examples/README.md](../../examples/README.md)** - Examples guide
- **[docs/SDD.md](../../docs/SDD.md)** - Full specification and design
- **[docs/GUIA_WSL_ASTERISK.md](../../docs/GUIA_WSL_ASTERISK.md)** - WSL guide

---

## License

MIT License - This setup is provided as an example for testing.

---

**Version**: 0.3.0
**Last Updated**: March 2026
**Status**: Production
