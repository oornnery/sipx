# SIPX - Modern SIP Library for Python

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A modern, intuitive SIP (Session Initiation Protocol) library for Python with a clean, declarative API.

## ✨ Features

- **🎯 Simple & Intuitive** - Clean API with declarative event handlers
- **🔐 Automatic Authentication** - Built-in digest authentication with auto-retry
- **📡 Multiple Transports** - UDP, TCP, and TLS support
- **🎨 Rich Console Output** - Beautiful CLI with colored output
- **🔄 State Management** - Automatic transaction and dialog tracking
- **📝 Full SIP Support** - INVITE, REGISTER, OPTIONS, MESSAGE, BYE, and more

## 🚀 Quick Start

```python
from sipx import Client, Events, Auth, event_handler

class MyEvents(Events):
    """Define your event handlers with decorators."""
    
    @event_handler('INVITE', status=200)
    def on_call_accepted(self, request, response, context):
        print("Call accepted!")
        print(f"SDP: {response.body}")

# Create client and make a call
with Client() as client:
    client.events = MyEvents()
    client.auth = Auth.Digest('alice', 'secret')
    response = client.invite('sip:bob@example.com', 'sip:alice@local')
```

That's it! Authentication, retries, and state management are all handled automatically.

## 📦 Installation

### Using uv (recommended)

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install sipx
uv pip install sipx

# Or add to your project
uv add sipx
```

### Using pip

```bash
pip install sipx
```

## 📚 Documentation

### Basic Usage

```python
from sipx import Client, Events, Auth, event_handler, SDPBody

# Define event handlers
class CallEvents(Events):
    def on_request(self, request, context):
        """Called before every request is sent."""
        print(f"→ Sending {request.method}")
        return request
    
    def on_response(self, response, context):
        """Called after every response is received."""
        print(f"← Received {response.status_code}")
        return response
    
    @event_handler('INVITE', status=180)
    def on_ringing(self, request, response, context):
        print("📞 Ringing...")
    
    @event_handler('INVITE', status=200)
    def on_accepted(self, request, response, context):
        print("✅ Call accepted!")

# Use the client
with Client(local_port=5060) as client:
    # Configure
    client.events = CallEvents()
    client.auth = Auth.Digest('alice', 'secret')
    
    # Create SDP
    sdp = SDPBody.offer(
        local_ip=client.local_address.host,
        local_port=8000,
        audio=True
    )
    
    # Make call
    response = client.invite('sip:bob@example.com', body=sdp.to_string())
    
    if response.status_code == 200:
        client.ack(response=response)
        # Call is active...
        client.bye(response=response)
```

### Registration

```python
with Client() as client:
    client.auth = Auth.Digest('alice', 'secret')
    
    # Host is auto-extracted from AOR
    response = client.register(aor='sip:alice@example.com')
    
    if response.status_code == 200:
        print("✓ Registered successfully!")
```

### Send Message

```python
with Client() as client:
    response = client.message(
        to_uri='sip:bob@example.com',
        content='Hello from SIPX!'
    )
```

### Check Server Status

```python
with Client() as client:
    response = client.options(uri='sip:example.com')
    print(f"Server: {response.headers.get('Server')}")
```

## 🎨 Event Handlers

The `@event_handler` decorator lets you handle specific SIP events:

```python
class MyEvents(Events):
    # Handle specific method and status
    @event_handler('INVITE', status=200)
    def on_invite_ok(self, request, response, context):
        pass
    
    # Handle multiple status codes
    @event_handler('INVITE', status=(401, 407))
    def on_auth_required(self, request, response, context):
        pass
    
    # Handle multiple methods
    @event_handler(('INVITE', 'MESSAGE'), status=200)
    def on_success(self, request, response, context):
        pass
    
    # Handle any status for a method
    @event_handler('REGISTER')
    def on_any_register(self, request, response, context):
        pass
    
    # Handle any method with specific status
    @event_handler(status=404)
    def on_not_found(self, request, response, context):
        pass
```

## 🔐 Authentication

Authentication is automatic when you set `client.auth`:

```python
# Simple
client.auth = Auth.Digest('username', 'password')

# With optional parameters
client.auth = Auth.Digest(
    username='alice',
    password='secret',
    realm='example.com',
    display_name='Alice Smith',
    user_agent='MyApp/1.0'
)
```

When the server challenges with 401/407, the client automatically:
1. Parses the challenge
2. Builds the authorization header
3. Retries the request
4. Returns the final response

## 🎯 Supported Methods

- **INVITE** - Establish calls
- **ACK** - Acknowledge INVITE responses
- **BYE** - Terminate calls
- **CANCEL** - Cancel pending INVITE
- **REGISTER** - Register with a server
- **OPTIONS** - Query server capabilities
- **MESSAGE** - Send instant messages
- **SUBSCRIBE** - Subscribe to events
- **NOTIFY** - Send event notifications
- **REFER** - Call transfer
- **INFO** - Mid-call information (DTMF)
- **UPDATE** - Session parameter updates
- **PRACK** - Provisional response acknowledgement
- **PUBLISH** - Publish event state

## 📖 Examples

Check out the `examples/` directory for more:

- [`simple_example.py`](examples/simple_example.py) - Minimal registration example
- [`simplified_demo.py`](examples/simplified_demo.py) - Complete demo with all features

Run the examples:

```bash
# Simple registration
uv run python examples/simple_example.py

# Full demo (requires Asterisk server)
uv run python examples/simplified_demo.py
```

## 🧪 Testing with Asterisk

Start an Asterisk server with Docker:

```bash
cd docker/asterisk
docker-compose up -d
```

Configure a user in `pjsip.conf`:

```ini
[alice]
type=endpoint
context=default
disallow=all
allow=ulaw
auth=alice
aors=alice

[alice]
type=auth
auth_type=userpass
password=secret
username=alice

[alice]
type=aor
max_contacts=1
```

Then run the examples against `192.168.1.100` (or your Asterisk IP).

## 🛠️ Development

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/sipx.git
cd sipx

# Install dependencies
uv sync

# Run tests
uv run pytest

# Run linting
uv run ruff check sipx
```

### Running Tests

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=sipx

# Specific test file
uv run pytest tests/test_client.py
```

## 📝 Advanced Usage

For advanced use cases, see the [Simplified API Documentation](docs/SIMPLIFIED_API.md).

Topics covered:
- Custom event handlers
- Transaction and dialog state access
- Manual authentication handling
- Transport configuration
- Error handling
- Migration from old API

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Rich](https://github.com/Textualize/rich) for beautiful console output
- Inspired by modern HTTP libraries like HTTPX
- RFC 3261 (SIP) and related RFCs for protocol implementation

## 📧 Contact

- **Issues**: [GitHub Issues](https://github.com/yourusername/sipx/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/sipx/discussions)

---

**Made with ❤️ for the SIP community**