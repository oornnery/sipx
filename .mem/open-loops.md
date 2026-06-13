# Open Loops

| id | question | options | needed decision |
| --- | --- | --- | --- |
| O1 | Next Asterisk media path after WebSocket MVP? | AudioSocket, ExternalMedia RTP | After WebSocket media MVP proves the first Asterisk media path. |
| O2 | First target user? | IVR QA, contact center app, technical SIP tester | Before product positioning beyond README. |
| O3 | First STT/TTS providers? | local fake, OpenAI, Deepgram, ElevenLabs, other | Before media/AI adapters. |
| O4 | Artifact retention policy? | local only, configurable TTL, encrypted storage | Before real recordings/transcripts. |
| O5 | Asterisk test environment? | Docker lab exists; external PBX optional | Before non-local integration expansion. |
| O6 | License? | MIT/Apache/proprietary/other | Before public distribution and Asterisk positioning. |
| O7 | Config format? | `harness.toml` profiles exist; YAML scenarios still optional | Before richer scenario runner UX. |
| O8 | SIP runtime next scope? | media wiring, live inspector, advanced dialogs | After current SPEC completion. |
| O9 | PJSIP runtime priority? | after SIP lab mode and Asterisk lab; only if interop demand appears | Before optional runtime work. |
| O11 | Slow AI media behavior? | silence, comfort tone, waiting prompt, configurable policy | Before real STT/TTS/LLM runtime. |
| O12 | Advanced RTP depth after fixed jitter buffer/session? | adaptive jitter, RTCP, impairment, payload validation | After CLI RTP metrics and basic audio modes prove operational behavior. |
| O13 | Next SIP/UAC/UAS layer after 1.11.0? | live SIP inspector, RFC4733 RTP DTMF send, recording/transcript capture | After event_hooks, summaries, compact headers, and CLI dry-run are validated. |
| O14 | Release draft policy? | keep latest draft only, publish manually, automate cleanup | Before first public `sipx` release is published. |
| O15 | LLM provider scope? | OpenAI-compatible client only, provider protocol, or vendor-specific adapters | Before building AI media agents beyond templates. |
| O16 | Reorg of duplicated SIP stacks? | unify on `protocol/` + remove `sip/` duplicate; `rfc/` renamed to `extensions/` in 3.2.0; `sip/` sans-I/O toolkit kept (unique parsers/builders) | Phase 2 partial done 3.2.0; full `sip/` removal still open if desired. |
| O17 | Security/RFC hardening roadmap? | P0 done 3.2.0; P1 part 1 done 3.4.0 (rport, non-2xx ACK, CANCEL); remaining P1 = §17 timers/retransmission (3.5.0); P2 = PRACK/100rel client, Digest SHA-256, dialog tag matching | Remaining P1 + P2 still open. |
