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
| O8 | Native SIP next scope? | media wiring, live inspector, advanced dialogs | After current SPEC completion. |
| O9 | PJSIP backend priority? | after native lab mode and Asterisk lab; only if interop demand appears | Before optional backend work. |
| O10 | Type-check gate? | fix `uv run ty check` diagnostics, sync system `python -m ty`, or defer hard gate | Before claiming full type-check validation. |
| O11 | Slow AI media behavior? | silence, comfort tone, waiting prompt, configurable policy | Before real STT/TTS/LLM runtime. |
| O12 | Advanced RTP depth? | jitter buffer, RTCP, impairment, payload validation | After basic RTP/DTMF primitives. |
| O13 | Next native SIP/softphone layer after 1.1.0? | media wiring, live inspector, recordings/transcripts | Before choosing work outside current SPEC table. |
| O14 | Remote replacement policy? | force-push master only, preserve/delete old tags, push new tags later | Before replacing `https://github.com/oornnery/sipx`. |
