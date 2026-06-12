# RFC Compliance Matrix

This document tracks compliance with targeted SIP and related RFCs. All
requirements start with "Planned" status and will be updated as implementation
tasks complete. No "full compliance" claims are made without test evidence.

---

## RFC 3261 - SIP: Session Initiation Protocol

**Status**: Implemented (partial coverage)
**Test Files**:
`tests/test_sip_message.py`,
`tests/test_protocol_transaction.py`,
`tests/test_protocol_dialog.py`,
`tests/test_client_uac.py`,
`tests/test_client_uas.py`,
`tests/test_client_lifecycle.py`,
`tests/test_sip_auth_requests.py`,
`tests/test_sip_transaction_dialog.py`
**Coverage**: ~75% (110+ tests across core parsing, transactions, dialogs, and
UAC/UAS)

**Limitations / Notes**:
- Proxy behavior and registrar binding refresh are not yet tested.
- Loop detection via Via branch is implemented but lacks dedicated test
coverage.
- Stateless proxy forwarding is not implemented.

Citation:
[https://datatracker.ietf.org/doc/html/rfc3261](https://datatracker.ietf.org/doc/html/rfc3261)

| Requirement | MUST/SHOULD/MAY | Status | Test Evidence |
|---|---|---|---|
| SIP message format (request/response line, headers, body) | MUST | Implemented | `tests/test_sip_message.py` |
| URI parsing and comparison rules | MUST | Implemented | `tests/test_sip_message.py` |
| Via header processing and branch parameter generation | MUST | Implemented | `tests/test_sip_message.py`, `tests/test_client_uac.py` |
| Contact header handling for routing | MUST | Implemented | `tests/test_protocol_dialog.py` |
| Record-Route and Route set construction | MUST | Implemented | `tests/test_protocol_dialog.py` |
| Call-ID, From, To tag generation and matching | MUST | Implemented | `tests/test_client_uac.py`, `tests/test_protocol_dialog.py` |
| CSeq header incrementing per direction | MUST | Implemented | `tests/test_client_uac.py` |
| INVITE client transaction state machine | MUST | Implemented | `tests/test_protocol_transaction.py` |
| INVITE server transaction state machine | MUST | Implemented | `tests/test_protocol_transaction.py` |
| Non-INVITE client transaction state machine | MUST | Implemented | `tests/test_protocol_transaction.py` |
| Non-INVITE server transaction state machine | MUST | Implemented | `tests/test_protocol_transaction.py` |
| ACK request generation for final responses | MUST | Implemented | `tests/test_protocol_transaction.py` |
| CANCEL request handling and 487 generation | MUST | Partial | `tests/test_sip_transaction_dialog.py` (limited) |
| Dialog creation from INVITE 2xx | MUST | Implemented | `tests/test_protocol_dialog.py` |
| Dialog creation from INVITE 101-199 with To tag | MUST | Implemented | `tests/test_protocol_dialog.py` |
| Dialog termination on BYE | MUST | Implemented | `tests/test_protocol_dialog.py` |
| REGISTER request handling and binding refresh | MUST | Partial | `tests/test_client_uac.py` (no refresh tests) |
| Registrar Contact expiry and unregistration | MUST | Partial | `tests/test_client_uac.py` (no expiry tests) |
| Stateless and stateful proxy behavior | SHOULD | Planned | |
| 100 Trying provisional response generation | SHOULD | Implemented | `tests/test_protocol_provisional.py` |
| Loop detection via Via branch and Max-Forwards | MUST | Partial | Implemented, no dedicated tests |
| Max-Forwards decrementing | MUST | Implemented | `tests/test_client_uac.py` |
| Timestamp header support | MAY | Planned | |
| Require and Supported header negotiation | MUST | Implemented | `tests/test_client_uac.py` |
| Unsupported header rejection | MUST | Implemented | `tests/test_client_uac.py` |
| Retry-After header for overloaded responses | SHOULD | Planned | |
| Error response generation (4xx, 5xx, 6xx) | MUST | Implemented | `tests/test_protocol_transaction.py` |

---

## RFC 3262 - Reliability of Provisional Responses in SIP

**Status**: Implemented
**Test File**: `tests/test_rfc_prack.py`
**Coverage**: ~85% (17 tests)

**Limitations / Notes**:
- Retransmission of unacknowledged reliable provisionals is not tested.
- Integration with offer/answer inside reliable provisionals is not tested.

Citation:
[https://datatracker.ietf.org/doc/html/rfc3262](https://datatracker.ietf.org/doc/html/rfc3262)

| Requirement | MUST/SHOULD/MAY | Status | Test Evidence |
|---|---|---|---|
| Supported: 100rel header advertisement | MUST | Implemented | `tests/test_rfc_prack.py` |
| Require: 100rel for reliable provisional negotiation | MUST | Implemented | `tests/test_rfc_prack.py` |
| PRACK method request generation | MUST | Implemented | `tests/test_rfc_prack.py` |
| PRACK method request reception and matching | MUST | Implemented | `tests/test_rfc_prack.py` |
| RSeq header numbering for reliable provisionals | MUST | Implemented | `tests/test_rfc_prack.py` |
| RAck header in PRACK matching RSeq and CSeq | MUST | Implemented | `tests/test_rfc_prack.py` |
| Retransmission of unacknowledged reliable provisionals | MUST | Partial | Not tested |
| 2xx response to PRACK | MUST | Implemented | `tests/test_rfc_prack.py` |
| Integration with offer/answer in reliable provisionals | MUST | Partial | Not tested |

---

## RFC 3263 - Locating SIP Servers

**Status**: Implemented
**Test File**: `tests/test_rfc_dns.py`
**Coverage**: ~90% (18 tests)

**Limitations / Notes**:
- All DNS lookups use mock records; no live NAPTR/SRV queries are exercised.
- A/AAAA fallback logic is present but not verified against real resolver
output.

Citation:
[https://datatracker.ietf.org/doc/html/rfc3263](https://datatracker.ietf.org/doc/html/rfc3263)

| Requirement | MUST/SHOULD/MAY | Status | Test Evidence |
|---|---|---|---|
| NAPTR DNS lookup for SIP transport selection | MUST | Partial | Mock only (`tests/test_rfc_dns.py`) |
| SRV record resolution for host/port | MUST | Partial | Mock only (`tests/test_rfc_dns.py`) |
| A/AAAA fallback when no SRV records exist | MUST | Partial | Logic present, not live-tested |
| Transport protocol selection priority | MUST | Implemented | `tests/test_rfc_dns.py` |
| Use of _sip._udp, _sip._tcp, _sips._tcp SRV prefixes | MUST | Implemented | `tests/test_rfc_dns.py` |
| Numeric IP address bypassing DNS lookup | MUST | Implemented | `tests/test_rfc_dns.py` |
| Default port selection (5060 UDP/TCP, 5061 TLS) | MUST | Implemented | `tests/test_rfc_dns.py` |

---

## RFC 3264 - Offer/Answer Model with SDP

**Status**: Partial (basic parsing and generation only)
**Test Files**: `tests/test_sdp.py`, `tests/test_sdp_parsing.py`
**Coverage**: ~45% (20 tests)

**Limitations / Notes**:
- Re-INVITE offer/answer for hold/resume is not implemented.
- Empty offer/answer (body-less re-INVITE) is not supported.
- bandwidth (b=) line parsing is present but not exercised in negotiation.
- Codec preference ordering is handled only for static payload types.

Citation:
[https://datatracker.ietf.org/doc/html/rfc3264](https://datatracker.ietf.org/doc/html/rfc3264)

| Requirement | MUST/SHOULD/MAY | Status | Test Evidence |
|---|---|---|---|
| SDP offer generation in initial INVITE | MUST | Implemented | `tests/test_sdp.py` |
| SDP answer generation in 2xx/1xx response | MUST | Implemented | `tests/test_sdp.py` |
| Media line (m=) matching between offer and answer | MUST | Implemented | `tests/test_sdp_parsing.py` |
| Attribute line (a=) interpretation per media | MUST | Implemented | `tests/test_sdp_parsing.py` |
| Direction attribute handling (sendrecv/sendonly/recvonly/inactive) | MUST | Implemented | `tests/test_sdp_parsing.py` |
| Codec preference ordering from offer to answer | MUST | Partial | `tests/test_sdp.py` (static types only) |
| RTP/AVP profile and payload type mapping | MUST | Implemented | `tests/test_sdp.py` |
| Re-INVITE offer/answer for hold/resume | MUST | Planned | |
| Rejection of media lines with port=0 | MUST | Partial | Logic present, no dedicated test |
| Re-INVITE with no body (empty offer/answer) | SHOULD | Planned | |
| bandwidth (b=) line interpretation | SHOULD | Partial | Parsed, not negotiated |

---

## RFC 3265/6665 - SIP-Specific Event Notification

**Status**: Implemented
**Test File**: `tests/test_rfc_events.py`
**Coverage**: ~85% (20 tests)

**Limitations / Notes**:
- Subscription expiration timeout handling is implemented but not tested with
real timers.
- Allow-Events header advertisement is not enforced in tests.

Citation:
[https://datatracker.ietf.org/doc/html/rfc3265](https://datatracker.ietf.org/doc/html/rfc3265)

| Requirement | MUST/SHOULD/MAY | Status | Test Evidence |
|---|---|---|---|
| SUBSCRIBE request generation and handling | MUST | Implemented | `tests/test_rfc_events.py` |
| NOTIFY request generation and handling | MUST | Implemented | `tests/test_rfc_events.py` |
| Event header with package name and id parameter | MUST | Implemented | `tests/test_rfc_events.py` |
| Subscription-State header (active/pending/terminated) | MUST | Implemented | `tests/test_rfc_events.py` |
| Expires header in SUBSCRIBE for duration | MUST | Implemented | `tests/test_rfc_events.py` |
| 200 OK response to SUBSCRIBE | MUST | Implemented | `tests/test_rfc_events.py` |
| 200 OK response to NOTIFY | MUST | Implemented | `tests/test_rfc_events.py` |
| Subscription refresh with new SUBSCRIBE | MUST | Implemented | `tests/test_rfc_events.py` |
| Subscription termination via Expires: 0 or NOTIFY | MUST | Implemented | `tests/test_rfc_events.py` |
| Allow-Events header advertisement | SHOULD | Partial | Not tested |
| Subscription expiration timeout handling | MUST | Partial | Logic present, timer not tested |

---

## RFC 3581 - Symmetric Response Routing (rport)

**Status**: Planned
**Test File**: (none)
**Coverage**: 0%

**Limitations / Notes**:
- Not yet implemented.

Citation:
[https://datatracker.ietf.org/doc/html/rfc3581](https://datatracker.ietf.org/doc/html/rfc3581)

| Requirement | MUST/SHOULD/MAY | Status | Test Evidence |
|---|---|---|---|
| Via rport parameter reception and processing | MUST | Planned | |
| Received parameter insertion for NAT traversal | MUST | Planned | |
| Response routing to rport source port when present | MUST | Planned | |
| rport parameter inclusion in request Via | SHOULD | Planned | |
| Symmetric response behavior for UDP | MUST | Planned | |
| Preservation of source IP in received parameter | MUST | Planned | |

---

## RFC 3856 - Presence in SIP

**Status**: Implemented
**Test File**: `tests/test_rfc_presence.py`
**Coverage**: ~85% (25 tests, covers RFC 3856 + 3858)

**Limitations / Notes**:
- Subscription authorization and policy logic is not implemented.
- Presence watcher/presenter role enforcement is not tested at the SIP layer.

Citation:
[https://datatracker.ietf.org/doc/html/rfc3856](https://datatracker.ietf.org/doc/html/rfc3856)

| Requirement | MUST/SHOULD/MAY | Status | Test Evidence |
|---|---|---|---|
| SUBSCRIBE/NOTIFY for presence event package | MUST | Implemented | `tests/test_rfc_presence.py` |
| Event: presence header handling | MUST | Implemented | `tests/test_rfc_presence.py` |
| Presence document content-type (application/pidf+xml) | MUST | Implemented | `tests/test_rfc_presence.py` |
| Presence state transitions (open/closed) | MUST | Implemented | `tests/test_rfc_presence.py` |
| Presence watcher and presenter roles | MUST | Partial | Roles parsed, not enforced |
| Subscription authorization and policy | SHOULD | Planned | |
| PIDF document parsing and generation | MUST | Implemented | `tests/test_rfc_presence.py` |

---

## RFC 3858 - Presence Information Data Format (PIDF)

**Status**: Implemented
**Test File**: `tests/test_rfc_presence.py`
**Coverage**: ~85% (shared with RFC 3856)

**Limitations / Notes**:
- XML schema validation is limited to namespace and well-formedness checks.
- Optional elements such as `<timestamp>` are parsed but not validated.

Citation:
[https://datatracker.ietf.org/doc/html/rfc3858](https://datatracker.ietf.org/doc/html/rfc3858)

| Requirement | MUST/SHOULD/MAY | Status | Test Evidence |
|---|---|---|---|
| PIDF XML namespace and schema compliance | MUST | Implemented | `tests/test_rfc_presence.py` |
| entity URI attribute in <presence> root | MUST | Implemented | `tests/test_rfc_presence.py` |
| <tuple> element with id and <status> child | MUST | Implemented | `tests/test_rfc_presence.py` |
| <basic> status values open/closed | MUST | Implemented | `tests/test_rfc_presence.py` |
| <contact> element for presentity address | SHOULD | Implemented | `tests/test_rfc_presence.py` |
| <timestamp> element for state freshness | MAY | Partial | Parsed, not validated |
| XML well-formedness validation | MUST | Implemented | `tests/test_rfc_presence.py` |
| PIDF serialization and parsing | MUST | Implemented | `tests/test_rfc_presence.py` |

---

## RFC 3428 - SIP MESSAGE Method

**Status**: Implemented
**Test File**: `tests/test_rfc_message.py`
**Coverage**: ~90% (14 tests)

**Limitations / Notes**:
- Session-mode MESSAGE (within dialog) is not tested.
- MIME multipart body support is not tested.
- `application/im-iscomposing` content-type is not explicitly handled.

Citation:
[https://datatracker.ietf.org/doc/html/rfc3428](https://datatracker.ietf.org/doc/html/rfc3428)

| Requirement | MUST/SHOULD/MAY | Status | Test Evidence |
|---|---|---|---|
| MESSAGE request generation and transmission | MUST | Implemented | `tests/test_rfc_message.py` |
| MESSAGE request reception and processing | MUST | Implemented | `tests/test_rfc_message.py` |
| 200 OK response to successful MESSAGE | MUST | Implemented | `tests/test_rfc_message.py` |
| Content-Type header for message body | MUST | Implemented | `tests/test_rfc_message.py` |
| text/plain and application/im-iscomposing support | SHOULD | Partial | text/plain tested |
| MESSAGE outside dialog (page-mode messaging) | MUST | Implemented | `tests/test_rfc_message.py` |
| MESSAGE within dialog (session-mode) | MAY | Planned | |
| MIME multipart body support | MAY | Planned | |
| Content-Length validation for MESSAGE bodies | MUST | Implemented | `tests/test_rfc_message.py` |

---

## RFC 5626 - Outbound Connections for SIP

**Status**: Implemented
**Test File**: `tests/test_rfc_outbound.py`
**Coverage**: ~70% (15 tests)

**Limitations / Notes**:
- STUN keep-alive is not implemented; only CRLF ping is supported.
- Flow failure detection and recovery is not tested.
- Multiple outbound flows to different edge proxies is not tested.
- GRUU support is not implemented.
- 439 First Hop Lacks Outbound Support response is not implemented.

Citation:
[https://datatracker.ietf.org/doc/html/rfc5626](https://datatracker.ietf.org/doc/html/rfc5626)

| Requirement | MUST/SHOULD/MAY | Status | Test Evidence |
|---|---|---|---|
| Outbound registration flow with reg-id and instance-id | MUST | Implemented | `tests/test_rfc_outbound.py` |
| Path header construction and preservation | MUST | Implemented | `tests/test_rfc_outbound.py` |
| Flow token generation and routing | MUST | Implemented | `tests/test_rfc_outbound.py` |
| Via received parameter handling for flows | MUST | Partial | Logic present, no dedicated test |
| Keep-alive mechanisms (STUN, CRLF) for flow | MUST | Partial | CRLF only (`tests/test_rfc_outbound.py`) |
| Flow failure detection and recovery | MUST | Partial | Not tested |
| Multiple outbound flows to different edge proxies | SHOULD | Planned | |
| GRUU (Globally Routable User Agent URI) support | MAY | Planned | |
| Instance-id (+sip.instance) Contact parameter | MUST | Implemented | `tests/test_rfc_outbound.py` |
| reg-id Contact parameter for flow ordering | MUST | Implemented | `tests/test_rfc_outbound.py` |
| 439 First Hop Lacks Outbound Support response | MUST | Planned | |
| Connection-oriented transport binding for flow | MUST | Implemented | `tests/test_rfc_outbound.py` |

---

*Last updated: 2026-06-12*
