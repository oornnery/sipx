# Open Loops

| id | question | options | needed decision |
| --- | --- | --- | --- |
| O1 | First Asterisk media path? | WebSocket media, AudioSocket, ExternalMedia RTP | Before AsteriskBackend MVP. |
| O2 | First target user? | IVR QA, contact center app, technical SIP tester | Before product positioning beyond README. |
| O3 | First STT/TTS providers? | local fake, OpenAI, Deepgram, ElevenLabs, other | Before media/AI adapters. |
| O4 | Artifact retention policy? | local only, configurable TTL, encrypted storage | Before real recordings/transcripts. |
| O5 | Asterisk test environment? | Docker, local package, external lab PBX | Before integration tests. |
| O6 | License? | MIT/Apache/proprietary/other | Before public distribution and Asterisk positioning. |
| O7 | Config format? | `harness.toml`, YAML scenarios, Python-only first | Before scenario runner UX. |
| O8 | Native SIP next scope? | transaction/dialog first, SDP/RTP first, or UAC/UAS runtime first | Parser primitives are done; decide next native SIP layer. |
| O9 | PJSIP backend priority? | before native lab mode, after native lab mode, never unless demanded | Before optional backend work. |
| O10 | Type-check environment? | install/sync `ty`, use existing executable, or defer type gate | Before claiming full validation gate. |
| O11 | Slow AI media behavior? | silence, comfort tone, waiting prompt, configurable policy | Before real STT/TTS/LLM runtime. |
| O12 | RTP/DTMF implementation depth? | packet parse only, stats first, RFC4733 full event encoder/decoder | Before completing T19-T20. |
