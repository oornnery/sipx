# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.4] - 2026-03-31

### Added

- **CLI** — `uv run sipx` entry point with typer: `register`, `options`, `call`, `message`, `listen`
- **Response builders** — `request.ok()`, `request.trying()`, `request.ringing()`, `request.error(code)`, `request.redirect(uri)`
- **Dialog tracking** — `DialogTracker` in `Client`/`AsyncClient`: implicit `ack()`/`bye()` without passing the response
- **Auto DNS SRV** — `Client(auto_dns=True)` resolves SIP URIs via RFC 3263 SRV + A fallback (default on)
- **`create_sdp(port)`** — client helper that generates `SDPBody.audio()` with local IP
- **Asterisk anonymous endpoint** — unauthenticated OPTIONS returns 200 OK (no 401 challenge)
- **5 new examples** — `response_builders.py`, `dialog_tracking.py`, `routing.py`, `dns_resolver.py`, `session_timers.py`
- **Integration tests** — `tests/integration/test_asterisk.py` smoke-tests against Asterisk Docker
- **CI/CD pipeline** — GitHub Actions: lint+test on PR, Asterisk integration, auto GitHub Release, PyPI publish via trusted publisher
- **Logging** — 23 previously-silent modules now emit structured logs via child loggers (`sipx.transport.udp`, `sipx.fsm`, `sipx.rtp`, etc.)

### Fixed

- **SIP URI port extraction** — replaced `urlparse` (which ignores `sip:` scheme) with `SipURI.parse`; explicit ports in URIs like `sip:host:5080` now work correctly
- **Timer A/E retransmission** — `_on_state_change()` was never called on transaction creation (constructor bypasses FSM side-effects); fixed by triggering after timer wiring
- **Request timeout** — sync `Client.request()` now returns `None` on timeout instead of raising `TimeoutError`
- **DNS SRV on IP addresses** — `SipResolver.resolve()` now skips SRV lookup for literal IPs (no more `_sip._udp.127.0.0.1` queries)
- **Ctrl+C responsiveness** — reduced sync poll interval from 500 ms to 100 ms so `KeyboardInterrupt` is handled within one tick (WSL2 / PEP 475)

### Changed

- `Client.request()` return type is now `Optional[Response]` (was `Response`)
- Log format for sent/received messages now includes `Call-ID` and direction (`>>>` / `<<<`)
- `examples/README.md` rewritten with all 22 examples categorized by use case
- `examples/asterisk.py` updated: `test_options_no_auth`, timing counters, `create_sdp()` usage

---

## [0.0.3] - 2025-01-27

### Fixed

- **Type Hints**: Fixed undefined name errors in `_types.py`
  - Added forward references for `Transaction` and `Dialog` classes in `TYPE_CHECKING` block
  - Resolved F821 lint errors for `TransactionCallback` and `DialogCallback` type aliases

### Changed

- **Code Quality**: All lint checks now pass cleanly
  - Fixed Ruff linting errors
  - Maintained code formatting standards

### Documentation

- Improved type safety and IDE support with proper forward references

---

## [0.0.2] - 2024

### Major Refactoring - Complete Architecture Overhaul

This release represents a complete refactoring of the sipx library, transforming it from a monolithic structure into a modular, extensible framework using Abstract Base Classes (ABC) and dedicated parsers.

### Added

#### Headers Module (`_header.py`)
- **`HeaderContainer` (ABC)**: Abstract base class for header container implementations
- **`HeaderParser`**: Dedicated parser for SIP headers
  - `parse()`: Parse raw header data
  - `parse_lines()`: Parse header lines with folding support
  - `parse_header_value()`: Parse header values into components
  - `format_header_value()`: Format header values with parameters

#### Message Module (`_message.py`)
- **`SIPMessage` (ABC)**: Abstract base class for all SIP messages
- **`MessageParser`**: Unified parser orchestrating all component parsers
  - `parse()`: Parse complete SIP messages
  - `parse_request()`: Parse SIP requests using HeaderParser and BodyParser
  - `parse_response()`: Parse SIP responses using HeaderParser and BodyParser
  - `parse_uri()`: Parse SIP URIs into components
- Lazy body parsing via `BodyParser` when `.body` is accessed
- Lazy auth challenge parsing via `AuthParser` when `.auth_challenge` is accessed

#### Body Module (`_body.py`)
- **`MessageBody` (ABC)**: Abstract base class for all message body types
- **`BodyParser`**: Content-Type based body parser
  - `parse()`: Auto-detect and parse based on Content-Type
  - `parse_sdp()`: Parse SDP bodies
  - `parse_multipart()`: Parse multipart bodies with recursive support
  - `parse_text()`, `parse_html()`, `parse_xml()`, etc.
- **Body Types**:
  - `SDPBody`: Session Description Protocol (RFC 4566)
    - Embedded origin fields (no separate `SDPOrigin` class)
    - Embedded media descriptions (no separate `SDPMedia` class)
    - `add_media()`: Add media descriptions
    - `add_attribute()`: Add session attributes
  - `TextBody`: Plain text bodies
  - `HTMLBody`: HTML content
  - `DTMFRelayBody`: DTMF signaling
  - `SIPFragBody`: SIP message fragments
  - `XMLBody`: XML documents (PIDF, conference-info, etc.)
  - `MultipartBody`: Multipart content with recursive parsing
  - `RawBody`: Unknown/unsupported content types

#### Authentication Module (`_auth.py`)
- **Abstract Base Classes**:
  - `AuthMethod` (ABC): Base for all authentication methods
  - `Challenge` (ABC): Base for authentication challenges
  - `Credentials` (ABC): Base for authentication credentials
- **`AuthParser`**: Unified authentication parser
  - `parse_challenge()`: Parse challenge from header (auto-detect scheme)
  - `parse_from_headers()`: Extract challenge from WWW-Authenticate/Proxy-Authenticate
  - `create_auth()`: Create appropriate AuthMethod from credentials and challenge

### Changed

#### Breaking Changes

**DigestAuth API**:
```python
# OLD (v0.1.x)
auth = DigestAuth(credentials=creds)
header = auth.build_authorization(method, uri, challenge=challenge)

# NEW (v0.2.0)
auth = DigestAuth(credentials=creds, challenge=challenge)
header = auth.build_authorization(method, uri)
```
- Challenge is now required in the `DigestAuth` constructor
- `build_authorization()` no longer accepts `challenge` parameter

**Module Structure**:
- `_models.py` (2000+ lines) split into `_models/` package:
  - `_models/_header.py`: Headers and HeaderParser
  - `_models/_message.py`: Request, Response, and MessageParser
  - `_models/_body.py`: Body types and BodyParser
  - `_models/_auth.py`: Authentication and AuthParser

**Internal Changes**:
- `Request.headers` and `Response.headers` now use internal `_headers` attribute
- Public `headers` property provides access (no user-facing change)

#### Enhanced

**Headers**:
- Better canonicalization algorithm
- Support for all SIP compact forms
- Improved line folding support (RFC 3261 Section 7.3.1)

**Messages**:
- Lazy body parsing (performance improvement)
- Lazy auth challenge parsing
- Auto-update Content-Length and Content-Type when body is set
- Better type hints and documentation

**Authentication**:
- Type-safe credential/challenge matching
- Support for multiple authentication schemes
- Easier to extend with new methods

### Improved

- **Extensibility**: All components use ABC for easy extension
- **Consistency**: Uniform pattern across all modules (ABC → Implementation → Parser)
- **Type Safety**: Better type hints and runtime checking
- **Documentation**: 4 comprehensive guides added:
  - `docs/ARCHITECTURE.md`: Complete architecture overview
  - `docs/AUTH_REFACTOR.md`: Authentication refactoring guide
  - `docs/BODY_CONTENT.md`: Body content handling guide
  - `docs/REFACTORING_SUMMARY.md`: Visual refactoring summary
- **Testing**: 278 passing tests covering all components
- **Performance**: Lazy parsing reduces overhead for simple messages

### Removed

**Legacy functions and classes**:
- `Parser` class - Use `MessageParser` instead
- `parse_auth_challenge()` function - Use `AuthParser.parse_from_headers()` instead
- `make_digest_response()` function - Use `DigestAuth` class instead

### Migration Guide

#### Required Changes

1. **Update DigestAuth usage**:
```python
# OLD
auth = DigestAuth(credentials=creds)
auth.build_authorization(method, uri, challenge=challenge)

# NEW
auth = DigestAuth(credentials=creds, challenge=challenge)
auth.build_authorization(method, uri)
```

#### Recommended Improvements

2. **Use parsers** (required):
```python
from sipx import MessageParser, AuthParser, HeaderParser

# Parse messages (Parser class removed)
msg = MessageParser.parse(data)

# Parse authentication (parse_auth_challenge removed)
challenge = AuthParser.parse_from_headers(response.headers)
auth = AuthParser.create_auth(credentials, challenge)

# Parse headers
headers = HeaderParser.parse(header_data)
```

3. **Use structured body types**:
```python
from sipx import SDPBody

# Create SDP
sdp = SDPBody(username="alice", session_id="123", address="192.168.1.1")
sdp.add_media(media="audio", port=49170, protocol="RTP/AVP", formats=["0", "8"])

# Set on message
request.body = sdp  # Auto-sets Content-Type and Content-Length

# Parse SDP from response
if isinstance(response.body, SDPBody):
    for media in response.body.media_descriptions:
        print(f"{media['media']} on port {media['port']}")
```

### Technical Details

**Lines of Code**:
- Before: `_models.py` (2000+ lines)
- After: 4 focused modules (~500 lines each)

**Test Results**:
- 278 tests passing ✅
- Full coverage of all components
- RFC 3261 compliance verified

**Performance**:
- Lazy body parsing: ~30% faster for messages without body access
- Lazy auth parsing: ~20% faster for non-auth responses
- Header canonicalization: Optimized for common headers

### Breaking Changes

- ❌ DigestAuth constructor signature changed (challenge now required)
- ❌ SDPOrigin and SDPMedia classes removed (use SDPBody directly)
- ❌ `Parser` class removed - Use `MessageParser` instead
- ❌ `parse_auth_challenge()` function removed - Use `AuthParser.parse_from_headers()` instead
- ❌ `make_digest_response()` function removed - Use `DigestAuth` class instead

### Future Plans

- Structured header types (Via, Contact, Route as objects)
- Multi-value header support (multiple Via, Route, Record-Route)
- OAuth 2.0 / Bearer token authentication
- Additional body types (JSON, custom XML schemas)
- Performance optimizations (header canonicalization cache, C extensions)
- Async parser support

---

## [0.0.1] - Initial Release

### Added
- Basic SIP message parsing
- Request and Response classes
- Headers container with case-insensitive access
- Digest authentication support
- Core SIP/2.0 protocol support

---

[0.0.4]: https://github.com/oornnery/sipx/compare/v0.0.3...v0.0.4
[0.0.3]: https://github.com/oornnery/sipx/compare/v0.0.2...v0.0.3
[0.0.2]: https://github.com/oornnery/sipx/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/oornnery/sipx/releases/tag/v0.0.1