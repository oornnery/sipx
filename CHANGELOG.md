# Changelog

## [0.2.0] - 2025-10-22

### Added

- Expanded `sipx.demo` to drive a full REGISTER → OPTIONS → INVITE → MESSAGE flow with Rich progress output and a summary panel.
- Introduced CLI switches `--skip-register`, `--skip-options`, `--skip-invite`, and `--skip-message` to make individual transactions optional.
- Added `--debug` flag to enable verbose logging and automatically surface raw SIP responses during troubleshooting.

### Changed

- Converted demo logging to Rich’s handler and f-strings, improving readability while keeping debug traces concise.
- Display MESSAGE/OPTIONS status buckets (success, provisional, timeout, rejection) directly in the Rich progress entries.
- Automatically send BYE when an INVITE succeeds to tidy up demo sessions.

### Fixed

- Prevent crash when provisional or error responses arrive after a call has already terminated, and avoid duplicate remote hangup events.
- Ensure INVITE authentication retries reuse consistent CSeq/branch values and update stored responses for diagnostics.
- Align ACK sequencing with authenticated INVITE requests and tolerate late non-success responses once a dialog is established.
