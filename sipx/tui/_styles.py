"""Textual CSS styles for sipx TUI — Posting-style flat design."""

APP_CSS = """\
/* ── Global ─────────────────────────────────────────── */

Screen {
    background: $background;
}

/* ── Sidebar ────────────────────────────────────────── */

#sidebar {
    width: auto;
    max-width: 28;
    dock: left;
    background: $surface;
}

#sidebar.hidden {
    display: none;
}

#sidebar-title {
    text-style: bold;
    color: $text-muted;
    padding: 0 1;
    height: 1;
    background: $surface-darken-1;
}

#collection-tree {
    height: 1fr;
    scrollbar-size: 1 1;
    background: transparent;
    color: $text 80%;
    width: 1fr;
}

#collection-tree:focus {
    color: $text;
}

/* ── Workspace ──────────────────────────────────────── */

#workspace {
    height: 1fr;
}

/* ── Main tabs ──────────────────────────────────────── */

#main-tabs {
    height: 1fr;
}

#tab-request {
    height: 1fr;
}

#tab-flows {
    height: 1fr;
}

#tab-capture {
    height: 1fr;
}

Tabs {
    height: 2;
}

/* ── Method bar ─────────────────────────────────────── */

#method-bar {
    height: 1;
    padding: 0;
    background: $surface;
}

#method-select {
    width: 14;
    height: 1;
    border: none;
    padding: 0;
    margin: 0;
}

#method-select SelectOverlay {
    width: 16;
}

#method-select:focus SelectCurrent {
    background: $accent;
}

#method-select SelectCurrent {
    height: 1;
    border: none;
    padding: 0 1;
    background: $primary-muted;
}

#method-select SelectCurrent .arrow {
    color: $text-muted;
}

#uri-input {
    width: 1fr;
    height: 1;
    border: none;
    padding: 0 1;
    margin: 0;
    background: $surface-lighten-1;
}

#uri-input:focus {
    border: none;
    background: $surface-lighten-2;
}

#uri-input.error {
    background: $error 20%;
}

#new-callid-btn {
    min-width: 4;
    width: 4;
    height: 1;
    border: none;
    padding: 0 1;
    margin: 0;
    background: $surface-lighten-1;
    color: $text-muted;
}

#new-callid-btn:hover {
    background: $primary;
    color: $text;
}

#response-status-code {
    width: auto;
    height: 1;
    padding: 0;
    margin: 0;
    text-style: bold;
}

#send-button {
    min-width: 8;
    height: 1;
    border: none;
    padding: 0 1;
    margin: 0;
    background: $accent-muted;
    color: $text;
    text-style: bold;
}

#send-button:hover {
    background: $accent;
}

#send-button:disabled {
    background: $surface;
    color: $text-muted;
}

.status-error {
    color: $error;
    background: $error-muted;
}

/* ── Request section ────────────────────────────────── */

#request-section {
    height: 2fr;
    min-height: 6;
    border: round $accent 40%;
    border-title-color: $text-muted;
    border-title-align: right;
}

#request-section:focus-within {
    border: round $accent;
    border-title-color: $text;
    border-title-style: bold;
}

#request-editor {
    height: 1fr;
}

#request-tabs {
    height: 1fr;
}

/* Header editor */

#header-editor {
    height: 1fr;
}

#request-headers {
    height: 1fr;
    scrollbar-size: 1 1;
    padding: 0 1;
}

#request-headers:focus {
    padding: 0;
    border-left: inner $accent;
}

#request-headers > .datatable--header {
    color: $success;
    background: $surface;
}

#request-headers > .datatable--cursor {
    background: $accent 20%;
}

#request-headers:blur > .datatable--cursor {
    background: transparent;
}

/* Header add bar */

#header-add-bar {
    height: 1;
    dock: bottom;
    padding: 0;
    background: $surface;
}

#header-add-bar #editing-label {
    width: auto;
    height: 1;
    padding: 0 1;
    color: $text-accent;
    display: none;
}

#header-add-bar.edit-mode {
    background: $accent-muted;
}

#header-add-bar.edit-mode #editing-label {
    display: block;
}

#header-add-bar.edit-mode Input {
    background: $accent 10%;
}

#header-add-bar Input {
    width: 1fr;
    height: 1;
    border: none;
    padding: 0 1;
    margin: 0;
    background: $surface-lighten-1;
}

#header-add-bar Input:focus {
    border: none;
    background: $surface-lighten-2;
}

#header-add-bar #new-header-name {
    width: 1fr;
    max-width: 28;
}

#header-add-bar #add-header-btn {
    min-width: 5;
    width: 5;
    height: 1;
    border: none;
    padding: 0 1;
    margin: 0;
    background: $primary;
    color: $text;
}

#header-add-bar #add-header-btn:hover {
    background: $primary-darken-1;
    text-style: bold;
}

/* Body editor */

#request-body {
    height: 1fr;
    border: none;
}

#request-body:focus {
    border: none;
}

/* Auth form */

#auth-form {
    height: auto;
    padding: 1 2;
    max-height: 8;
}

#auth-form Label {
    margin: 0;
    color: $text-muted;
    height: 1;
}

#auth-form Input {
    height: 1;
    border: none;
    padding: 0 1;
    margin: 0 0 1 0;
    background: $surface-lighten-1;
}

#auth-form Input:focus {
    border: none;
    background: $surface-lighten-2;
}

/* ── Response section (split: ladder | raw+headers) ── */

#response-section {
    height: 3fr;
    min-height: 6;
    border: round $accent 40%;
    border-title-color: $text-muted;
    border-title-align: right;
}

#response-section:focus-within {
    border: round $accent;
    border-title-color: $text;
    border-title-style: bold;
}

/* Request tab ladder (left side of response) */
#req-ladder {
    width: 1fr;
    height: 1fr;
}

#req-ladder #ladder-ep-header {
    height: 1;
    padding: 0 1;
    color: $text-muted;
    background: $surface-darken-1;
}

#req-ladder #ladder-rows {
    height: 1fr;
    scrollbar-size: 1 1;
    background: transparent;
}

/* Request tab response viewer (right side) */
#req-response {
    width: 2fr;
    height: 1fr;
    border-left: solid $surface-lighten-1;
}

#response-tabs {
    height: 1fr;
}

#raw-view {
    height: 1fr;
    scrollbar-size: 1 1;
    padding: 0 1;
}

#response-headers {
    height: 1fr;
    scrollbar-size: 1 1;
    padding: 0 1;
}

#response-headers:focus {
    padding: 0;
    border-left: inner $accent;
}

#response-headers > .datatable--header {
    color: $success;
    background: $surface;
}

/* ── Capture tab — two pages ───────────────────────── */

/* Page 1: Dialog list */
#capture-list-page {
    height: 1fr;
    border: round $accent 40%;
    border-title-color: $text-muted;
    border-title-align: right;
}

#capture-list-page:focus-within {
    border: round $accent;
    border-title-color: $text;
    border-title-style: bold;
}

#packet-table {
    height: 1fr;
    scrollbar-size: 1 1;
    padding: 0;
    background: transparent;
}

#packet-table:focus {
    background: transparent;
}

/* Page 2: Dialog detail */
#capture-detail-page {
    height: 1fr;
    border: round $accent 40%;
    border-title-color: $text-muted;
    border-title-align: right;
}

#capture-detail-page:focus-within {
    border: round $accent;
    border-title-color: $text;
    border-title-style: bold;
}

#capture-detail-bar {
    height: 1;
    background: $surface;
    padding: 0;
}

#capture-back-btn {
    height: 1;
    min-width: 10;
    border: none;
    padding: 0 1;
    margin: 0;
    background: $primary-muted;
    color: $text;
}

#capture-back-btn:hover {
    background: $primary;
}

#capture-detail-title {
    width: 1fr;
    height: 1;
    padding: 0 1;
    text-style: bold;
}

#capture-detail-content {
    height: 1fr;
}

/* Capture ladder (left side of detail) */
#cap-ladder {
    width: 1fr;
    height: 1fr;
}

#cap-ladder #ladder-ep-header {
    height: 1;
    padding: 0 1;
    color: $text-muted;
    background: $surface-darken-1;
}

#cap-ladder #ladder-rows {
    height: 1fr;
    scrollbar-size: 1 1;
    background: transparent;
}

/* Capture raw/detail (right side) */
#capture-right-tabs {
    width: 2fr;
    height: 1fr;
    border-left: solid $surface-lighten-1;
}

#cap-raw-view {
    height: 1fr;
    scrollbar-size: 1 1;
    padding: 0 1;
}

#cap-detail-view {
    height: 1fr;
    scrollbar-size: 1 1;
    padding: 0 1;
}

/* ── Flow panel ─────────────────────────────────────── */

#flow-panel {
    height: 1fr;
}

#flow-toolbar {
    height: 1;
    background: $surface;
    padding: 0;
}

#flow-toolbar Button {
    height: 1;
    border: none;
    padding: 0 2;
    margin: 0;
    min-width: 10;
    background: $primary-muted;
    color: $text;
}

#flow-toolbar Button:hover {
    background: $primary;
}

#flow-toolbar #flow-run-btn {
    background: $accent-muted;
}

#flow-toolbar #flow-run-btn:hover {
    background: $accent;
}

#flow-progress {
    width: 1fr;
    height: 1;
}

#flow-editor-section {
    height: 2fr;
    min-height: 6;
    border: round $accent 40%;
    border-title-color: $text-muted;
    border-title-align: right;
}

#flow-editor-section:focus-within {
    border: round $accent;
    border-title-color: $text;
    border-title-style: bold;
}

#flow-editor {
    height: 1fr;
    border: none;
}

#flow-editor:focus {
    border: none;
}

#flow-log-section {
    height: 1fr;
    min-height: 4;
    border: round $accent 40%;
    border-title-color: $text-muted;
    border-title-align: right;
}

#flow-log-section:focus-within {
    border: round $accent;
    border-title-color: $text;
    border-title-style: bold;
}

#flow-log {
    height: 1fr;
    scrollbar-size: 1 1;
    padding: 0 1;
}

/* ── Log panel (global bottom drawer) ──────────────── */

#log-panel {
    dock: bottom;
    height: 10;
    max-height: 14;
    background: $surface;
    border-top: solid $accent 40%;
}

#log-panel-title {
    height: 1;
    text-style: bold;
    color: $text-muted;
    padding: 0 1;
    background: $surface-darken-1;
}

#global-log {
    height: 1fr;
    scrollbar-size: 1 1;
    padding: 0 1;
}

/* ── Auth toggle ────────────────────────────────────── */

#auth-toggle-row {
    height: 1;
    padding: 0 1;
    align-vertical: middle;
}

#auth-toggle-row Label {
    width: auto;
    margin: 0 1 0 0;
}

#auth-toggle {
    height: 1;
}

#auth-fields {
    padding: 0 1;
}

/* ── Loading indicator ──────────────────────────────── */

#response-loading {
    height: 1fr;
}

/* ── Status bar ─────────────────────────────────────── */

#status-bar {
    dock: bottom;
    height: 1;
    background: $surface;
    padding: 0;
    color: $text-muted;
}

#status-text {
    width: auto;
    height: 1;
    padding: 0 1;
}

#status-sparkline {
    width: 20;
    height: 1;
    min-width: 10;
}

/* ── TextArea global ────────────────────────────────── */

TextArea {
    border: none;
}

TextArea:focus {
    border: none;
}

/* ── Status colors ──────────────────────────────────── */

.status-1xx { color: $text-muted; }
.status-2xx { color: $success; background: $success-muted; }
.status-3xx { color: $warning; background: $warning-muted; }
.status-4xx { color: $error; background: $error-muted; }
.status-5xx { color: $error; background: $error-muted; text-style: bold; }
.status-6xx { color: $error; background: $error-muted; text-style: bold italic; }
.status-none { color: $text-muted; text-style: italic; }

/* ── Utility ────────────────────────────────────────── */

.hidden {
    display: none;
}
"""
