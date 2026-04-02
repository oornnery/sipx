# SPEC: TUI Request & Capture Redesign

## Overview

Redesign the Request and Capture tabs for better SIP workflow, inspired by sngrep's two-page flow. Add a global Log panel (bottom drawer) that replaces per-tab logs.

## Current State

```text
Request tab:
+----------------------------------+
| [METHOD ▾] [sip:uri...]  [Send] |
| Headers | Body | Auth           |
|   (header table)                 |
+----------------------------------+
| Raw | Headers | Dialog | Log     |
|   (response content)             |
+----------------------------------+

Capture tab (split):
+----------------------------------+
| ▶ INVITE 0.0.0.0 → x (11 msgs) |
+----------------------------------+
| Ladder | Log  |  Raw | Detail    |
| ▶ OPT  ...   |  SIP/2.0 ...    |
+----------------------------------+
```

## Target State

### Request Tab

Split response section into left (Dialog/Ladder) + right (Raw/Headers):

```text
+----------------------------------------------+
| [METHOD ▾] [sip:uri...]  [🔄] [200 OK] [Send] |
| Headers | Body | Auth                         |
|   Via    SIP/2.0/UDP ...              ✕       |
|   From   <sip:user@host>;tag=abc      ✕       |
|   ...                                         |
+----------------------------------------------+
| Dialog              |  Raw | Headers          |
| ▶ 0.001s OPTIONS    |  OPTIONS sip:... SIP/2.0|
| ◀ 0.250s 200 OK     |  Via: SIP/2.0/UDP ...  |
|                      |  From: <sip:...>       |
|                      |  Call-ID: abc@host     |
+----------------------------------------------+
```

- **Left**: Dialog tree (ladder-style) showing all transactions for the current Call-ID. Click to navigate.
- **Right**: `Raw` (full SIP message text) and `Headers` (parsed table) tabs — updates on dialog selection.
- **🔄 button**: Generate new Call-ID (resets dialog, new auto-headers).
- Remove `Dialog` and `Log` tabs from response section.

### Capture Tab — Two-Page Flow (sngrep-style)

**Page 1 — Dialog List** (main view):

```text
+----------------------------------------------+
|  Capture                                      |
| ▶ INVITE  0.0.0.0:0 → 192.168.1.1:5060       |
|     (4 msgs)  200 OK                          |
| ▶ OPTIONS 0.0.0.0:0 → 207.202.17.250:5060    |
|     (2 msgs)  200 OK                          |
+----------------------------------------------+
```

Click/Enter on a dialog → switches to Page 2.

**Page 2 — Dialog Detail** (replaces list):

```text
+----------------------------------------------+
| ← Back  INVITE 0.0.0.0 → 192.168.1.1        |
+----------------------------------------------+
| Ladder              |  Raw | Detail           |
| ▶ 0.001s INVITE     |  INVITE sip:bob SIP/2.0|
| ◀ 0.010s 100 Trying |  Via: SIP/2.0/UDP ...  |
| ◀ 0.050s 200 OK     |  From: <sip:...>       |
| ▶ 0.051s ACK        |  ...                   |
+----------------------------------------------+
```

- `Escape` or `← Back` button returns to Page 1.
- Ladder + Raw/Detail layout same as current capture detail.

### Global Log Panel (Bottom Drawer)

```text
+----------------------------------------------+
| [any tab content above]                       |
+----------------------------------------------+
| ▼ Log                                    [✕]  |
| ▶ OPTIONS sip:062099137@proxy2...             |
| ◀ 200 OK (825.0ms)                           |
| ▶ Flow: invite-test started                  |
|   ✓ Step 1: INVITE sent                      |
+----------------------------------------------+
| Pkts: 4  │  Dlgs: 2  │  ready                |
+----------------------------------------------+
```

- Toggle with `Ctrl+L` (repurpose from "Clear") or a keybinding.
- Shows ALL logs: Request sends, Flow execution, errors.
- Sits between content and status bar, docked bottom.
- Can be closed with Escape or toggle key.

## Requirements

### Functional

- FR-01: Request tab response section splits into Dialog (left) + Raw/Headers (right)
- FR-02: Dialog panel shows all transactions for current Call-ID as a clickable ladder
- FR-03: Clicking a transaction updates Raw and Headers on the right
- FR-04: 🔄 button in method bar generates new Call-ID and refreshes auto-headers
- FR-05: Capture tab main page shows dialog list (PacketTable tree)
- FR-06: Clicking a dialog in Capture opens detail page (Ladder + Raw/Detail)
- FR-07: Escape/Back button returns from detail to dialog list
- FR-08: Global Log panel (bottom drawer) shows all log messages
- FR-09: Log panel toggleable via keybinding
- FR-10: Flow execution logs appear in global Log panel

### Non-Functional

- NFR-01: No layout changes to Flows tab
- NFR-02: Keyboard navigation (vim h/l for tabs, j/k for lists) preserved
- NFR-03: Status bar stays at very bottom, below Log panel

## Component Changes

### Widgets to modify

| Widget | Change |
|---|---|
| `ResponseSection` | Remove Dialog/Log tabs. Keep Raw + Headers only |
| `MethodBar` | Add 🔄 (new Call-ID) button |
| `PacketTable` | Extract to work as page 1 of Capture |
| `StatusBar` | No change |

### New Widgets

| Widget | Purpose |
|---|---|
| `RequestDialog` | Left panel in Request tab — ladder of current dialog transactions |
| `CaptureListPage` | Page 1: PacketTable (dialog list) |
| `CaptureDetailPage` | Page 2: Ladder + Raw/Detail for selected dialog |
| `LogPanel` | Bottom drawer, global log, toggleable |

## Implementation Plan

1. Create `LogPanel` widget (bottom drawer, replaces per-tab logs)
2. Refactor `ResponseSection` → remove Dialog/Log, keep Raw + Headers
3. Create `RequestDialog` widget (ladder for current Call-ID)
4. Wire Request tab: compose left (RequestDialog) + right (ResponseSection)
5. Add 🔄 button to `MethodBar` for new Call-ID generation
6. Create `CaptureListPage` / `CaptureDetailPage` with page switching
7. Wire Capture tab: page 1 ↔ page 2 transitions
8. Update `_app.py` compose and event handlers
9. Update CSS styles
10. Remove old Log references, wire `_log` to `LogPanel`

## Acceptance Criteria

- [ ] Request tab shows Dialog ladder (left) + Raw/Headers (right) in response area
- [ ] Clicking a dialog entry updates Raw and Headers
- [ ] 🔄 button generates new Call-ID and refreshes headers
- [ ] Capture tab shows dialog list; clicking opens detail page
- [ ] Escape from detail page returns to list
- [ ] Global Log panel toggleable, shows all log messages
- [ ] Flow execution logs appear in global Log panel
- [ ] Vim navigation (h/l tabs, j/k lists) still works
