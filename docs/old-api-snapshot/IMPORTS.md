# Old API Imports

This document lists all files that import from the old API modules (`sipx.uac`, `sipx.uas`, `sipx.ua`).

These files will need to be updated during the migration to the new `AsyncClient` API (Task 29).

## Files Importing from Old API

### Core Library

- **sipx/__init__.py**
  - `from sipx.ua import (EventHooks, SipCall, SipCallError, SipCallState, SipIncomingInvite, SipInviteAttempt, SipProvisionalResponse, SipRegisterError, SipRetransmissionPolicy, SipUacRuntime, SipUasRuntime, SipUserAgent, SipWireRuntime)`
  - `from sipx.uac import SipUac, SipUacError`
  - `from sipx.uas import SipUas, SipUasError`

### Applications

- **apps/cli/src/sipx_cli/main.py**
  - `from sipx.ua import EventHooks, SipRetransmissionPolicy, SipUserAgent`
  - `from sipx.uac import SipUac`
  - `from sipx.uas import SipUas`

- **apps/scenarios/examples/mizu/mizu_common.py**
  - `from sipx.ua import EventHooks`

### Tests

- **tests/test_uac_uas.py**
  - `from sipx.uac import SipUac as ModuleSipUac`
  - `from sipx.uas import SipUas as ModuleSipUas`

## Internal Dependencies

The old API files themselves have internal dependencies:

- **sipx/uac.py** imports from `sipx.ua`
- **sipx/uas.py** imports from `sipx.ua`

## Migration Notes

The old API files (`sipx/uac.py`, `sipx/uas.py`, `sipx/ua.py`) will be deleted in Task 32 (Wave 10).

All files listed above will need to be migrated to use the new `AsyncClient` API before that deletion occurs.
