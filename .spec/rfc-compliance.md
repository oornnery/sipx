# RFC Compliance Matrix

This document tracks compliance with targeted SIP and related RFCs. All requirements start with "Planned" status and will be updated as implementation tasks complete. No "full compliance" claims are made without test evidence.

---

## RFC 3261 - SIP: Session Initiation Protocol

Citation: [https://datatracker.ietf.org/doc/html/rfc3261](https://datatracker.ietf.org/doc/html/rfc3261)

| Requirement | MUST/SHOULD/MAY | Status | Test Evidence |
|---|---|---|---|
| SIP message format (request/response line, headers, body) | MUST | Planned | |
| URI parsing and comparison rules | MUST | Planned | |
| Via header processing and branch parameter generation | MUST | Planned | |
| Contact header handling for routing | MUST | Planned | |
| Record-Route and Route set construction | MUST | Planned | |
| Call-ID, From, To tag generation and matching | MUST | Planned | |
| CSeq header incrementing per direction | MUST | Planned | |
| INVITE client transaction state machine | MUST | Planned | |
| INVITE server transaction state machine | MUST | Planned | |
| Non-INVITE client transaction state machine | MUST | Planned | |
| Non-INVITE server transaction state machine | MUST | Planned | |
| ACK request generation for final responses | MUST | Planned | |
| CANCEL request handling and 487 generation | MUST | Planned | |
| Dialog creation from INVITE 2xx | MUST | Planned | |
| Dialog creation from INVITE 101-199 with To tag | MUST | Planned | |
| Dialog termination on BYE | MUST | Planned | |
| REGISTER request handling and binding refresh | MUST | Planned | |
| Registrar Contact expiry and unregistration | MUST | Planned | |
| Stateless and stateful proxy behavior | SHOULD | Planned | |
| 100 Trying provisional response generation | SHOULD | Planned | |
| Loop detection via Via branch and Max-Forwards | MUST | Planned | |
| Max-Forwards decrementing | MUST | Planned | |
| Timestamp header support | MAY | Planned | |
| Require and Supported header negotiation | MUST | Planned | |
| Unsupported header rejection | MUST | Planned | |
| Retry-After header for overloaded responses | SHOULD | Planned | |
| Error response generation (4xx, 5xx, 6xx) | MUST | Planned | |

---

## RFC 3262 - Reliability of Provisional Responses in SIP

Citation: [https://datatracker.ietf.org/doc/html/rfc3262](https://datatracker.ietf.org/doc/html/rfc3262)

| Requirement | MUST/SHOULD/MAY | Status | Test Evidence |
|---|---|---|---|
| Supported: 100rel header advertisement | MUST | Planned | |
| Require: 100rel for reliable provisional negotiation | MUST | Planned | |
| PRACK method request generation | MUST | Planned | |
| PRACK method request reception and matching | MUST | Planned | |
| RSeq header numbering for reliable provisionals | MUST | Planned | |
| RAck header in PRACK matching RSeq and CSeq | MUST | Planned | |
| Retransmission of unacknowledged reliable provisionals | MUST | Planned | |
| 2xx response to PRACK | MUST | Planned | |
| Integration with offer/answer in reliable provisionals | MUST | Planned | |

---

## RFC 3263 - Locating SIP Servers

Citation: [https://datatracker.ietf.org/doc/html/rfc3263](https://datatracker.ietf.org/doc/html/rfc3263)

| Requirement | MUST/SHOULD/MAY | Status | Test Evidence |
|---|---|---|---|
| NAPTR DNS lookup for SIP transport selection | MUST | Planned | |
| SRV record resolution for host/port | MUST | Planned | |
| A/AAAA fallback when no SRV records exist | MUST | Planned | |
| Transport protocol selection priority | MUST | Planned | |
| Use of _sip._udp, _sip._tcp, _sips._tcp SRV prefixes | MUST | Planned | |
| Numeric IP address bypassing DNS lookup | MUST | Planned | |
| Default port selection (5060 UDP/TCP, 5061 TLS) | MUST | Planned | |

---

## RFC 3264 - Offer/Answer Model with SDP

Citation: [https://datatracker.ietf.org/doc/html/rfc3264](https://datatracker.ietf.org/doc/html/rfc3264)

| Requirement | MUST/SHOULD/MAY | Status | Test Evidence |
|---|---|---|---|
| SDP offer generation in initial INVITE | MUST | Planned | |
| SDP answer generation in 2xx/1xx response | MUST | Planned | |
| Media line (m=) matching between offer and answer | MUST | Planned | |
| Attribute line (a=) interpretation per media | MUST | Planned | |
| Direction attribute handling (sendrecv/sendonly/recvonly/inactive) | MUST | Planned | |
| Codec preference ordering from offer to answer | MUST | Planned | |
| RTP/AVP profile and payload type mapping | MUST | Planned | |
| Re-INVITE offer/answer for hold/resume | MUST | Planned | |
| Rejection of media lines with port=0 | MUST | Planned | |
| Re-INVITE with no body (empty offer/answer) | SHOULD | Planned | |
| bandwidth (b=) line interpretation | SHOULD | Planned | |

---

## RFC 3265 - SIP-Specific Event Notification

Citation: [https://datatracker.ietf.org/doc/html/rfc3265](https://datatracker.ietf.org/doc/html/rfc3265)

| Requirement | MUST/SHOULD/MAY | Status | Test Evidence |
|---|---|---|---|
| SUBSCRIBE request generation and handling | MUST | Planned | |
| NOTIFY request generation and handling | MUST | Planned | |
| Event header with package name and id parameter | MUST | Planned | |
| Subscription-State header (active/pending/terminated) | MUST | Planned | |
| Expires header in SUBSCRIBE for duration | MUST | Planned | |
| 200 OK response to SUBSCRIBE | MUST | Planned | |
| 200 OK response to NOTIFY | MUST | Planned | |
| Subscription refresh with new SUBSCRIBE | MUST | Planned | |
| Subscription termination via Expires: 0 or NOTIFY | MUST | Planned | |
| Allow-Events header advertisement | SHOULD | Planned | |
| Subscription expiration timeout handling | MUST | Planned | |

---

## RFC 3581 - Symmetric Response Routing (rport)

Citation: [https://datatracker.ietf.org/doc/html/rfc3581](https://datatracker.ietf.org/doc/html/rfc3581)

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

Citation: [https://datatracker.ietf.org/doc/html/rfc3856](https://datatracker.ietf.org/doc/html/rfc3856)

| Requirement | MUST/SHOULD/MAY | Status | Test Evidence |
|---|---|---|---|
| SUBSCRIBE/NOTIFY for presence event package | MUST | Planned | |
| Event: presence header handling | MUST | Planned | |
| Presence document content-type (application/pidf+xml) | MUST | Planned | |
| Presence state transitions (open/closed) | MUST | Planned | |
| Presence watcher and presenter roles | MUST | Planned | |
| Subscription authorization and policy | SHOULD | Planned | |
| PIDF document parsing and generation | MUST | Planned | |

---

## RFC 3858 - Presence Information Data Format (PIDF)

Citation: [https://datatracker.ietf.org/doc/html/rfc3858](https://datatracker.ietf.org/doc/html/rfc3858)

| Requirement | MUST/SHOULD/MAY | Status | Test Evidence |
|---|---|---|---|
| PIDF XML namespace and schema compliance | MUST | Planned | |
| entity URI attribute in <presence> root | MUST | Planned | |
| <tuple> element with id and <status> child | MUST | Planned | |
| <basic> status values open/closed | MUST | Planned | |
| <contact> element for presentity address | SHOULD | Planned | |
| <timestamp> element for state freshness | MAY | Planned | |
| XML well-formedness validation | MUST | Planned | |
| PIDF serialization and parsing | MUST | Planned | |

---

## RFC 3428 - SIP MESSAGE Method

Citation: [https://datatracker.ietf.org/doc/html/rfc3428](https://datatracker.ietf.org/doc/html/rfc3428)

| Requirement | MUST/SHOULD/MAY | Status | Test Evidence |
|---|---|---|---|
| MESSAGE request generation and transmission | MUST | Planned | |
| MESSAGE request reception and processing | MUST | Planned | |
| 200 OK response to successful MESSAGE | MUST | Planned | |
| Content-Type header for message body | MUST | Planned | |
| text/plain and application/im-iscomposing support | SHOULD | Planned | |
| MESSAGE outside dialog (page-mode messaging) | MUST | Planned | |
| MESSAGE within dialog (session-mode) | MAY | Planned | |
| MIME multipart body support | MAY | Planned | |
| Content-Length validation for MESSAGE bodies | MUST | Planned | |

---

## RFC 5626 - Outbound Connections for SIP

Citation: [https://datatracker.ietf.org/doc/html/rfc5626](https://datatracker.ietf.org/doc/html/rfc5626)

| Requirement | MUST/SHOULD/MAY | Status | Test Evidence |
|---|---|---|---|
| Outbound registration flow with reg-id and instance-id | MUST | Planned | |
| Path header construction and preservation | MUST | Planned | |
| Flow token generation and routing | MUST | Planned | |
| Via received parameter handling for flows | MUST | Planned | |
| Keep-alive mechanisms (STUN, CRLF) for flow | MUST | Planned | |
| Flow failure detection and recovery | MUST | Planned | |
| Multiple outbound flows to different edge proxies | SHOULD | Planned | |
| GRUU (Globally Routable User Agent URI) support | MAY | Planned | |
| Instance-id (+sip.instance) Contact parameter | MUST | Planned | |
| reg-id Contact parameter for flow ordering | MUST | Planned | |
| 439 First Hop Lacks Outbound Support response | MUST | Planned | |
| Connection-oriented transport binding for flow | MUST | Planned | |

---

*Last updated: 2026-06-11*
