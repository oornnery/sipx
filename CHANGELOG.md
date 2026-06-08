# CHANGELOG

## 0.8.0 - 2026-06-08

- Added real async UDP SIP transport with typed RX/TX wire events, size limits, receive timeouts, and fail-closed parse errors.
- Added `NativeSipBackend` with real UDP `start`/`stop`, `send_request`, `send_response`, strict-mode raw-send rejection, lab-mode raw datagrams, and SIP timeline recording.
- Exported native SIP backend and UDP wire primitives from public package modules.
- Added loopback UDP tests for request/response exchange, timeline events, malformed datagrams, strict raw-send rejection, and receive timeout handling.
- Kept full T21 open: integrated strict UAC/UAS call flows and transaction retransmission timers remain pending.

## 0.7.3 - 2026-06-08

- Added sans-I/O REGISTER client flow with `ready`, `challenged`, `registered`, `unregistered`, and `failed` states.
- Added Digest challenge handling for 401/407 REGISTER responses and authenticated retry generation without storing passwords.
- Added unregister request creation via `Expires: 0`.
- Added tests for initial REGISTER, Digest auth retry, success/failure states, unregister, and missing challenge errors.
- Kept full T21 open: native sockets/timers, strict runtime, and integrated call flows remain pending.

## 0.7.2 - 2026-06-08

- Added UAS-side INVITE dialog creation from inbound requests.
- Added INVITE server transaction skeleton with provisional, success final, failure final, and failure ACK handling.
- Added BYE request creation helper using dialog identity and local CSeq progression.
- Added tests for UAS dialogs, INVITE server transaction state, ACK branch validation, BYE request creation, and dialog termination.
- Kept full T21 open: complete REGISTER client flow, sockets/timers, strict runtime, and integrated call flows remain pending.

## 0.7.1 - 2026-06-08

- Added non-INVITE client transaction skeleton.
- Added REGISTER request creation helper.
- Added SIP Digest challenge parsing and authorization header generation.
- Added tests for REGISTER headers, non-INVITE final response handling, and RFC Digest response generation.
- Kept full T21 open: UAS behavior, BYE flow, sockets/timers, strict runtime, and complete REGISTER client flow remain pending.

## 0.7.0 - 2026-06-08

- Added sans-I/O SIP dialog skeleton with dialog IDs, tag extraction, state transitions, and local CSeq progression.
- Added INVITE client transaction skeleton with provisional/success/failure response handling.
- Added related ACK and CANCEL request creation for INVITE transactions.
- Added tests for INVITE transaction state, ACK/CANCEL creation, dialog tags/state, and header tag parsing.
- Left full T21 open: UAS behavior, non-INVITE transactions, REGISTER, Digest auth, sockets/timers, and strict runtime are still pending.

## 0.6.0 - 2026-06-08

- Added RTP packet parse/serialize primitives for RTP v2 packets.
- Added RTP sequence statistics for received packets, gaps/loss, out-of-order packets, highest sequence, and SSRC.
- Added RFC4733 DTMF encode/decode helpers and `DtmfEvent` validation.
- Added RTP and DTMF tests.

## 0.5.0 - 2026-06-08

- Added SDP session/audio model, parser, and serializer.
- Added audio offer/answer helpers for PCMU, PCMA, and `telephone-event`.
- Added SDP direction handling for `sendrecv`, `sendonly`, `recvonly`, and `inactive`.
- Added tests for SDP parsing, serialization, offer/answer codec selection, direction inversion, and negotiation failure.

## 0.4.0 - 2026-06-08

- Added sans-I/O SIP URI, header map, message parser, and serializer primitives.
- Added typed `SipParseError` and parser bounds via `max_size`.
- Added Content-Length validation and serializer rewrite behavior.
- Added tests for SIP URI round-trip, compact header expansion, request/response parsing, Content-Length mismatch, oversized messages, and serialization.

## 0.3.0 - 2026-06-08

- Added media primitives: `AudioFrame`, `MediaPort`, STT/TTS protocols, `TranscriptEvent`, and barge-in policy.
- Added central redaction utilities for sensitive mapping values and SIP/ARI/SDP text lines.
- Connected `ArtifactStore` JSON/text writes to the default redactor.
- Added tests for media frame validation, barge-in policy, transcript confidence validation, redaction, and artifact redaction.
- Recorded redaction replacement bug in `SPEC.md` §B B2 and fixed it under invariant V13.

## 0.2.0 - 2026-06-08

- Added the initial `sipx` Python package with public exports for `Harness`, `Actor`, `Scenario`, `expect`, `Timeline`, `Verdict`, `Artifact`, metrics, and backend capabilities.
- Added `MockBackend` for network-free scenarios with mock call start, SIP final response, DTMF, and hangup timeline events.
- Added scenario execution with minimum artifacts: `timeline.jsonl` and `verdict.json`.
- Added minimal CLI entrypoint: `sipx scenario run <file>`.
- Added unit tests for timeline ordering, artifact/verdict generation, unsupported capabilities, expectation failures, harness execution, and CLI scenario loading.
- Updated `AGENTS.md` with the preferred delivery pipeline: small commit blocks, version bump, changelog, TODO/state/memory updates, validation, explicit staging.

## 0.1.0 - 2026-06-08

- Added initial project planning/spec state for `sipx`.
- Defined product direction as a Python programmable Voice/SIP Harness with Asterisk and Native SIP backends.
