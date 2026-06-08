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
| O8 | Native SIP scope for v0.1? | parser only, UAC only, UAC+UAS, REGISTER included | Before backend implementation. |
| O9 | PJSIP backend priority? | before native lab mode, after native lab mode, never unless demanded | Before optional backend work. |
