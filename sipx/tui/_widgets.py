"""Custom Textual widgets for sipx TUI — Posting-inspired, flat design."""

from __future__ import annotations

import uuid
from typing import Any

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Label,
    ProgressBar,
    RichLog,
    Rule,
    Select,
    Sparkline,
    Static,
    Switch,
    TabbedContent,
    TabPane,
    TextArea,
    Tree,
)

from ._capture import CapturedPacket, Direction, PacketStore

# ── SIP Methods ─────────────────────────────────────────────────────────────

SIP_METHODS: list[str] = [
    "INVITE",
    "REGISTER",
    "OPTIONS",
    "BYE",
    "ACK",
    "CANCEL",
    "MESSAGE",
    "SUBSCRIBE",
    "NOTIFY",
    "REFER",
    "INFO",
    "UPDATE",
    "PRACK",
    "PUBLISH",
]

AUTO_HEADER_NAMES: set[str] = {
    "Via",
    "From",
    "To",
    "Call-ID",
    "CSeq",
    "Contact",
    "Max-Forwards",
}


# ── Vim-like TabbedContent ──────────────────────────────────────────────────


class SipxTabs(TabbedContent):
    """TabbedContent with h/l vim navigation."""

    BINDINGS = [
        Binding("l", "next_tab", "Next tab", show=False),
        Binding("h", "previous_tab", "Prev tab", show=False),
    ]

    def action_next_tab(self) -> None:
        self.query_one("Tabs").action_next_tab()

    def action_previous_tab(self) -> None:
        self.query_one("Tabs").action_previous_tab()


# ── Method bar ──────────────────────────────────────────────────────────────


class MethodBar(Horizontal):
    """Top bar: [METHOD ▾] [sip:uri...] [🔄] [status badge] [Send]"""

    class SendPressed(Message):
        """Fired when Send button is clicked."""

    class NewCallIdPressed(Message):
        """Fired when 🔄 button is clicked to regenerate Call-ID."""

    class RequestChanged(Message):
        def __init__(self, method: str, uri: str) -> None:
            super().__init__()
            self.method = method
            self.uri = uri

    def compose(self) -> ComposeResult:
        yield Select(
            [(m, m) for m in SIP_METHODS],
            value="INVITE",
            id="method-select",
            allow_blank=False,
        )
        yield Input(placeholder="sip:user@host:port", id="uri-input")
        yield Button("\u21bb", id="new-callid-btn")
        yield Label("", id="response-status-code")
        yield Button("Send", id="send-button")

    def show_status(self, code: int, reason: str, elapsed_ms: float) -> None:
        lbl = self.query_one("#response-status-code", Label)
        lbl.update(f" {code} {reason} {elapsed_ms:.1f}ms ")
        lbl.remove_class(
            "status-1xx",
            "status-2xx",
            "status-3xx",
            "status-4xx",
            "status-5xx",
            "status-none",
        )
        lbl.add_class(f"status-{code // 100}xx")

    def clear_status(self) -> None:
        lbl = self.query_one("#response-status-code", Label)
        lbl.update("")
        lbl.set_classes("")

    def show_error(self, text: str) -> None:
        lbl = self.query_one("#response-status-code", Label)
        lbl.update(f" {text} ")
        lbl.set_classes("status-error")
        self.query_one("#uri-input", Input).add_class("error")

    def clear_error(self) -> None:
        self.query_one("#uri-input", Input).remove_class("error")

    @on(Button.Pressed, "#send-button")
    def _on_send(self) -> None:
        self.post_message(self.SendPressed())

    @on(Button.Pressed, "#new-callid-btn")
    def _on_new_callid(self) -> None:
        self.post_message(self.NewCallIdPressed())

    @on(Input.Submitted, "#uri-input")
    def _on_enter(self) -> None:
        self.post_message(self.SendPressed())

    @on(Input.Changed, "#uri-input")
    def _on_uri_changed(self) -> None:
        self._emit_change()

    @on(Select.Changed, "#method-select")
    def _on_method_changed(self) -> None:
        self._emit_change()

    def _emit_change(self) -> None:
        method = str(self.query_one("#method-select", Select).value or "INVITE")
        uri = self.query_one("#uri-input", Input).value
        if uri:
            self.post_message(self.RequestChanged(method, uri))


# ── Header editor ───────────────────────────────────────────────────────────


class HeaderEditor(Container):
    """Editable header key-value list with collapsible sections."""

    DEFAULT_HEADERS: list[tuple[str, str]] = [
        ("User-Agent", "sipx-tui/0.0.5"),
    ]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._rows: list[tuple[str, str]] = list(self.DEFAULT_HEADERS)
        self._editing: int | None = None

    def compose(self) -> ComposeResult:
        yield DataTable(id="request-headers")
        with Horizontal(id="header-add-bar"):
            yield Label("", id="editing-label")
            yield Input(placeholder="Header-Name", id="new-header-name")
            yield Input(placeholder="value", id="new-header-value")
            yield Button("+", id="add-header-btn")

    def on_mount(self) -> None:
        ht = self.query_one("#request-headers", DataTable)
        ht.add_columns("Header", "Value", "")
        ht.cursor_type = "row"
        ht.zebra_stripes = True
        self._rebuild_table()

    def _rebuild_table(self) -> None:
        ht = self.query_one("#request-headers", DataTable)
        ht.clear()
        for i, (name, val) in enumerate(self._rows):
            ht.add_row(name, val, "\u2715", key=str(i))

    def _set_edit_mode(self, editing: bool, row: int | None = None) -> None:
        bar = self.query_one("#header-add-bar", Horizontal)
        lbl = self.query_one("#editing-label", Label)
        btn = self.query_one("#add-header-btn", Button)
        if editing and row is not None:
            bar.add_class("edit-mode")
            lbl.update(f"Editing #{row + 1}")
            btn.label = "\u2713"
            self._editing = row
        else:
            bar.remove_class("edit-mode")
            lbl.update("")
            btn.label = "+"
            self._editing = None

    @on(Button.Pressed, "#add-header-btn")
    def _on_add(self) -> None:
        name_input = self.query_one("#new-header-name", Input)
        val_input = self.query_one("#new-header-value", Input)
        name = name_input.value.strip()
        val = val_input.value.strip()
        if not name:
            return
        if self._editing is not None and 0 <= self._editing < len(self._rows):
            self._rows[self._editing] = (name, val)
        else:
            self._rows.append((name, val))
        self._set_edit_mode(False)
        self._rebuild_table()
        name_input.value = ""
        val_input.value = ""
        name_input.focus()

    @on(Input.Submitted, "#new-header-name")
    def _on_name_submit(self) -> None:
        self.query_one("#new-header-value", Input).focus()

    @on(Input.Submitted, "#new-header-value")
    def _on_value_submit(self) -> None:
        self._on_add()

    @on(DataTable.RowSelected, "#request-headers")
    def _on_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key is None:
            return
        try:
            idx = int(event.row_key.value)
        except (ValueError, TypeError):
            return

        ht = self.query_one("#request-headers", DataTable)
        if ht.cursor_column == 2:
            if 0 <= idx < len(self._rows):
                self._rows.pop(idx)
                if self._editing == idx:
                    self._set_edit_mode(False)
                    self.query_one("#new-header-name", Input).value = ""
                    self.query_one("#new-header-value", Input).value = ""
                elif self._editing is not None and self._editing > idx:
                    self._editing -= 1
                self._rebuild_table()
            return

        if 0 <= idx < len(self._rows):
            name, val = self._rows[idx]
            self.query_one("#new-header-name", Input).value = name
            self.query_one("#new-header-value", Input).value = val
            self._set_edit_mode(True, idx)
            self.query_one("#new-header-name", Input).focus()

    def get_headers(self) -> dict[str, str]:
        return {n: v for n, v in self._rows if n and v}

    def get_call_id(self) -> str:
        """Return current Call-ID from headers."""
        return self.get_headers().get("Call-ID", "")

    def populate_from_uri(self, method: str, uri: str) -> None:
        """Auto-generate required SIP headers from method + URI."""
        user = ""
        host = "0.0.0.0"
        bare = uri
        if bare.startswith(("sip:", "sips:")):
            bare = bare.split(":", 1)[1]
        if "@" in bare:
            user, host_part = bare.rsplit("@", 1)
            host = host_part.split(";")[0].split("?")[0]
        else:
            host = bare.split(";")[0].split("?")[0]

        tag = uuid.uuid4().hex[:8]
        call_id = f"{uuid.uuid4().hex[:20]}@{host}"
        branch = f"z9hG4bK{uuid.uuid4().hex[:16]}"

        auto = {
            "Via": f"SIP/2.0/UDP {host};branch={branch};rport",
            "From": f"<{uri}>;tag={tag}",
            "To": f"<{uri}>",
            "Call-ID": call_id,
            "CSeq": f"1 {method}",
            "Contact": f"<{uri}>",
            "Max-Forwards": "70",
        }

        new_rows = [(n, v) for n, v in auto.items()]
        new_rows.extend((n, v) for n, v in self._rows if n not in AUTO_HEADER_NAMES)
        self._rows = new_rows
        if self._table_ready:
            self._set_edit_mode(False)
            self._rebuild_table()

    def regenerate_call_id(self) -> None:
        """Generate a new Call-ID keeping other headers intact."""
        # Find existing host from current headers
        host = "0.0.0.0"
        for name, val in self._rows:
            if name == "Call-ID" and "@" in val:
                host = val.split("@", 1)[1]
                break

        new_call_id = f"{uuid.uuid4().hex[:20]}@{host}"
        new_branch = f"z9hG4bK{uuid.uuid4().hex[:16]}"

        for i, (name, val) in enumerate(self._rows):
            if name == "Call-ID":
                self._rows[i] = ("Call-ID", new_call_id)
            elif name == "Via":
                # Update branch in Via
                parts = val.split(";")
                new_parts = []
                for p in parts:
                    if p.startswith("branch="):
                        new_parts.append(f"branch={new_branch}")
                    else:
                        new_parts.append(p)
                self._rows[i] = ("Via", ";".join(new_parts))

        if self._table_ready:
            self._rebuild_table()

    def set_headers(self, headers: dict[str, str]) -> None:
        self._rows = [(k, v) for k, v in headers.items()]
        if self._table_ready:
            self._rebuild_table()

    @property
    def _table_ready(self) -> bool:
        try:
            self.query_one("#request-headers", DataTable)
            return True
        except Exception:
            return False


# ── Request section ─────────────────────────────────────────────────────────


class RequestSection(Container):
    """Tabbed request editor — Headers, Body, Auth."""

    def compose(self) -> ComposeResult:
        with SipxTabs(id="request-tabs"):
            with TabPane("Headers", id="tab-req-headers"):
                yield HeaderEditor(id="header-editor")
            with TabPane("Body", id="tab-req-body"):
                yield TextArea(language="json", theme="monokai", id="request-body")
            with TabPane("Auth", id="tab-req-auth"):
                yield Vertical(
                    Horizontal(
                        Label("Enable Auth"),
                        Switch(id="auth-toggle", value=False),
                        id="auth-toggle-row",
                    ),
                    Rule(),
                    Vertical(
                        Label("Username"),
                        Input(id="auth-user", placeholder="alice"),
                        Label("Password"),
                        Input(id="auth-pass", placeholder="secret", password=True),
                        id="auth-fields",
                    ),
                    id="auth-form",
                )

    def on_mount(self) -> None:
        self._update_auth_fields()

    @on(Switch.Changed, "#auth-toggle")
    def _on_auth_toggle(self, event: Switch.Changed) -> None:
        self._update_auth_fields()

    def _update_auth_fields(self) -> None:
        enabled = self.query_one("#auth-toggle", Switch).value
        fields = self.query_one("#auth-fields", Vertical)
        fields.display = enabled

    def get_headers(self) -> dict[str, str]:
        return self.query_one("#header-editor", HeaderEditor).get_headers()

    def get_body(self) -> str:
        return self.query_one("#request-body", TextArea).text

    def get_auth(self) -> tuple[str, str]:
        if not self.query_one("#auth-toggle", Switch).value:
            return "", ""
        return (
            self.query_one("#auth-user", Input).value,
            self.query_one("#auth-pass", Input).value,
        )


# ── SIP raw rendering (sngrep-style syntax highlight) ──────────────────────


def render_sip_raw(pkt: CapturedPacket, store: PacketStore) -> list[Text]:
    """Render a SIP packet with sngrep-style coloring.

    Returns a list of Rich Text lines ready for RichLog.write().
    """
    import datetime

    lines: list[Text] = []

    # Header line: date src → dst (colored)
    # Use capture timestamp (monotonic) offset from wall clock
    elapsed = store.elapsed(pkt)
    ts = datetime.datetime.now(tz=datetime.timezone.utc)
    arrow = "\u2192" if pkt.direction == Direction.SENT else "\u2190"
    hdr_color = "green" if pkt.direction == Direction.SENT else "magenta"

    header = Text()
    header.append(
        f"{ts:%Y/%m/%d %H:%M:%S}.{elapsed:.6f} ",
        style=hdr_color,
    )
    header.append(f"{pkt.src} {arrow} {pkt.dst}", style=hdr_color)
    lines.append(header)

    # Parse and colorize the SIP message
    raw_lines = pkt.decoded.replace("\r\n", "\n").split("\n")
    in_body = False

    for raw_line in raw_lines:
        if not raw_line and not in_body:
            in_body = True
            lines.append(Text(""))
            continue

        if in_body:
            lines.append(Text(raw_line, style="dim"))
            continue

        t = Text()

        if raw_line == raw_lines[0]:
            # Request/Status line
            if raw_line.startswith("SIP/"):
                # Status line: SIP/2.0 200 OK
                parts = raw_line.split(None, 2)
                t.append(parts[0], style="white")
                if len(parts) >= 2:
                    t.append(f" {parts[1]}", style="green bold")
                if len(parts) >= 3:
                    t.append(f" {parts[2]}", style="green bold")
            else:
                # Request line: METHOD URI SIP/2.0
                parts = raw_line.split(None, 2)
                t.append(parts[0], style="green bold")
                if len(parts) >= 2:
                    t.append(f" {parts[1]}", style="white")
                if len(parts) >= 3:
                    t.append(f" {parts[2]}", style="white")
        elif ":" in raw_line:
            # Header line: Name: value
            name, _, val = raw_line.partition(":")
            name_lower = name.strip().lower()
            # Color based on header type
            if name_lower in ("from", "f"):
                name_style = "green"
            elif name_lower in ("to", "t"):
                name_style = "magenta"
            elif name_lower in ("call-id", "i"):
                name_style = "yellow"
            elif name_lower in ("cseq",):
                name_style = "cyan"
            elif name_lower in ("via", "v"):
                name_style = "cyan"
            else:
                name_style = "white"
            t.append(f"{name}:", style=name_style)
            t.append(f" {val.strip()}", style=name_style)
        else:
            t.append(raw_line, style="white")

        lines.append(t)

    return lines


def write_sip_raw(log: RichLog, pkt: CapturedPacket, store: PacketStore) -> None:
    """Write sngrep-style SIP raw to a RichLog widget."""
    log.clear()
    for line in render_sip_raw(pkt, store):
        log.write(line)


# ── Response section (Raw + Headers only) ──────────────────────────────────


class ResponseSection(Container):
    """Tabbed response viewer — Raw and Headers."""

    def compose(self) -> ComposeResult:
        with SipxTabs(id="response-tabs"):
            with TabPane("Raw", id="tab-raw"):
                yield RichLog(id="raw-view", markup=True)
            with TabPane("Headers", id="tab-resp-headers"):
                yield DataTable(id="response-headers")

    def on_mount(self) -> None:
        ht = self.query_one("#response-headers", DataTable)
        ht.add_columns("Header", "Value")
        ht.cursor_type = "row"
        ht.zebra_stripes = True

    def show_packet(self, pkt: CapturedPacket, store: PacketStore) -> None:
        """Display a packet's raw content and parsed headers."""
        write_sip_raw(self.query_one("#raw-view", RichLog), pkt, store)

        # Headers table
        ht = self.query_one("#response-headers", DataTable)
        ht.clear()
        text = pkt.decoded
        lines = text.replace("\r\n", "\n").split("\n")
        for line in lines[1:]:
            if not line:
                break
            if ":" in line:
                name, _, val = line.partition(":")
                ht.add_row(name.strip(), val.strip())

    def clear(self) -> None:
        """Clear both views."""
        self.query_one("#raw-view", RichLog).clear()
        self.query_one("#response-headers", DataTable).clear()


# ── SIP Ladder (sngrep-style drawn diagram) ────────────────────────────────


def _ladder_color(pkt: CapturedPacket) -> str:
    """Rich color for ladder arrow based on packet type."""
    if pkt.method:
        return "cyan bold"
    if pkt.status_code < 200:
        return "dim"
    if pkt.status_code < 300:
        return "green bold"
    if pkt.status_code < 400:
        return "yellow"
    return "red bold"


class SipLadder(Container):
    """sngrep-style interactive SIP ladder diagram.

    Renders a visual call flow with arrows between endpoints::

          0.0.0.0:38991             207.202.17.250:5060
               │                           │
      0.012s   │  ──── OPTIONS ─────────▶  │
      0.228s   │  ◀────── 200 OK ───────   │
    """

    class PacketSelected(Message):
        def __init__(self, index: int) -> None:
            super().__init__()
            self.index = index

    def __init__(self, store: PacketStore, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._store = store
        self._current_call_id: str = ""

    def compose(self) -> ComposeResult:
        yield Static("", id="ladder-ep-header")
        yield Tree("Ladder", id="ladder-rows")

    def on_mount(self) -> None:
        tree = self.query_one("#ladder-rows", Tree)
        tree.show_root = False
        tree.guide_depth = 0
        tree.root.expand()

    def show_dialog(self, call_id: str, force: bool = False) -> None:
        """Populate the ladder with packets from a dialog."""
        if not force and call_id == self._current_call_id:
            return
        self._current_call_id = call_id

        header = self.query_one("#ladder-ep-header", Static)
        tree = self.query_one("#ladder-rows", Tree)
        tree.root.remove_children()

        store = self._store
        dialog = store.get_dialog(call_id)
        if not dialog:
            header.update("")
            tree.root.add_leaf("[dim]No packets[/dim]")
            return

        # Collect unique endpoints
        endpoints: list[str] = []
        seen: set[str] = set()
        for pkt in dialog:
            for ep in (pkt.src, pkt.dst):
                if ep not in seen:
                    seen.add(ep)
                    endpoints.append(ep)

        pkt_index = {id(p): i for i, p in enumerate(store.packets)}

        if len(endpoints) == 2:
            left, right = endpoints[0], endpoints[1]
            # Header line with endpoint names
            hdr = Text()
            hdr.append(f"{'':>10s}  ", style="dim")
            hdr.append(f"{left}", style="bold")
            hdr.append(f"{'':>4s}", style="dim")
            hdr.append(f"{right}", style="bold")
            header.update(hdr)

            for pkt in dialog:
                elapsed = store.elapsed(pkt)
                idx = pkt_index.get(id(pkt), 0)
                color = _ladder_color(pkt)
                summary = pkt.summary

                label = Text()
                label.append(f"{elapsed:>8.3f}s", style="dim")
                label.append("  \u2502  ", style="dim")

                if pkt.src == left:
                    # Left → Right
                    label.append(
                        f"\u2500\u2500\u2500\u2500 {summary} "
                        f"\u2500\u2500\u2500\u2500\u25b6",
                        style=color,
                    )
                else:
                    # Right → Left
                    label.append(
                        f"\u25c0\u2500\u2500\u2500\u2500 {summary} "
                        f"\u2500\u2500\u2500\u2500",
                        style=color,
                    )

                label.append("  \u2502", style="dim")
                tree.root.add_leaf(label, data={"pkt_idx": idx})
        else:
            # Multi-endpoint fallback
            header.update("")
            for pkt in dialog:
                elapsed = store.elapsed(pkt)
                idx = pkt_index.get(id(pkt), 0)
                color = _ladder_color(pkt)

                label = Text()
                label.append(f"{elapsed:>8.3f}s", style="dim")
                label.append(f"  {pkt.src} ", style="")

                if pkt.direction == Direction.SENT:
                    label.append(
                        f"\u2500\u2500 {pkt.summary} \u2500\u2500\u25b6",
                        style=color,
                    )
                else:
                    label.append(
                        f"\u25c0\u2500\u2500 {pkt.summary} \u2500\u2500",
                        style=color,
                    )

                label.append(f" {pkt.dst}", style="")
                tree.root.add_leaf(label, data={"pkt_idx": idx})

    def clear(self) -> None:
        """Clear the ladder display."""
        self._current_call_id = ""
        self.query_one("#ladder-ep-header", Static).update("")
        self.query_one("#ladder-rows", Tree).root.remove_children()

    @on(Tree.NodeSelected, "#ladder-rows")
    def _on_selected(self, event: Tree.NodeSelected) -> None:
        node = event.node
        if node.data and isinstance(node.data, dict) and "pkt_idx" in node.data:
            self.post_message(self.PacketSelected(node.data["pkt_idx"]))


# ── Dialog tree (capture view — dialog list) ───────────────────────────────


def _status_style(code: int) -> str:
    """Rich style for a SIP status code."""
    if code < 200:
        return "dim"
    if code < 300:
        return "green"
    if code < 400:
        return "yellow"
    return "red"


class PacketTable(Tree):
    """Tree showing dialogs grouped by Call-ID (sngrep-style).

    Each root node is a dialog — expand to see all transactions.
    Clicking a dialog node opens the detail page.
    """

    BINDINGS = [
        Binding("c", "copy_packet", "Copy", show=False),
    ]

    class PacketSelected(Message):
        def __init__(self, index: int) -> None:
            super().__init__()
            self.index = index

    class DialogOpened(Message):
        """User opened a dialog — switch to detail page."""

        def __init__(self, call_id: str) -> None:
            super().__init__()
            self.call_id = call_id

    def __init__(self, store: PacketStore, **kwargs: Any) -> None:
        super().__init__("Dialogs", **kwargs)
        self._store = store
        self._pkt_count = 0

    def on_mount(self) -> None:
        self.root.expand()
        self.guide_depth = 2
        self.show_root = False

    def refresh_packets(self) -> None:
        """Rebuild tree when new packets arrive."""
        if len(self._store.packets) == self._pkt_count:
            return
        self._rebuild()

    def _rebuild(self) -> None:
        store = self._store
        new_count = len(store.packets)

        # Remember expanded dialogs
        expanded: set[str] = set()
        for node in self.root.children:
            if node.is_expanded and isinstance(node.data, dict):
                cid = node.data.get("call_id", "")
                if cid:
                    expanded.add(cid)

        self.root.remove_children()

        # Build packet → index map
        pkt_index: dict[int, int] = {id(p): i for i, p in enumerate(store.packets)}

        for call_id in store.call_ids:
            dialog = store.get_dialog(call_id)
            if not dialog:
                continue

            first = dialog[0]
            last = dialog[-1]
            method = first.method or "???"
            count = len(dialog)

            state = ""
            if last.status_code:
                style = _status_style(last.status_code)
                state = f"  [{style}]{last.summary}[/]"

            label = (
                f"[bold]{method}[/bold]  "
                f"{first.src} \u2192 {first.dst}  "
                f"[dim]({count} msgs)[/dim]"
                f"{state}"
            )

            node = self.root.add(label, data={"call_id": call_id})

            for pkt in dialog:
                elapsed = store.elapsed(pkt)
                pkt_idx = pkt_index.get(id(pkt), 0)
                dir_mark = (
                    "[cyan]\u25b6[/cyan]"
                    if pkt.direction == Direction.SENT
                    else "[green]\u25c0[/green]"
                )
                pkt_style = _status_style(pkt.status_code) if pkt.status_code else ""
                if pkt_style:
                    summary_markup = f"[{pkt_style}][bold]{pkt.summary}[/bold][/]"
                else:
                    summary_markup = f"[bold]{pkt.summary}[/bold]"
                pkt_label = (
                    f"{dir_mark} {elapsed:.3f}s  "
                    f"{summary_markup}  "
                    f"[dim]{pkt.size}B[/dim]"
                )
                node.add_leaf(pkt_label, data={"pkt_idx": pkt_idx})

            if call_id in expanded or call_id not in expanded:
                node.expand()

        # Orphan packets
        orphans = [p for p in store.packets if not p.call_id]
        if orphans:
            orphan_node = self.root.add(
                f"[dim]No Call-ID ({len(orphans)} pkts)[/dim]",
                data={"call_id": ""},
                expand=True,
            )
            for pkt in orphans:
                elapsed = store.elapsed(pkt)
                pkt_idx = pkt_index.get(id(pkt), 0)
                dir_mark = (
                    "[cyan]\u25b6[/cyan]"
                    if pkt.direction == Direction.SENT
                    else "[green]\u25c0[/green]"
                )
                orphan_node.add_leaf(
                    f"{dir_mark} {elapsed:.3f}s  [bold]{pkt.summary}[/bold]  "
                    f"[dim]{pkt.size}B[/dim]",
                    data={"pkt_idx": pkt_idx},
                )

        self._pkt_count = new_count

    @on(Tree.NodeSelected)
    def _on_node_selected(self, event: Tree.NodeSelected) -> None:
        """Select a packet or open a dialog detail page."""
        node = event.node
        if not node.data or not isinstance(node.data, dict):
            return

        if "pkt_idx" in node.data:
            self.post_message(self.PacketSelected(node.data["pkt_idx"]))
        elif "call_id" in node.data and node.data["call_id"]:
            self.post_message(self.DialogOpened(node.data["call_id"]))

    def action_copy_packet(self) -> None:
        node = self.cursor_node
        if node and isinstance(node.data, dict) and "pkt_idx" in node.data:
            idx = node.data["pkt_idx"]
            if 0 <= idx < len(self._store.packets):
                self.app.copy_to_clipboard(self._store.packets[idx].decoded)
                self.app.notify("Packet copied to clipboard")


# ── Collection tree ─────────────────────────────────────────────────────────


class CollectionTree(Tree):
    """Sidebar tree for saved profiles and flows."""

    BINDINGS = [
        Binding("delete,backspace", "delete_item", "Delete", show=False),
        Binding("n", "new_request", "New", show=False),
    ]

    class ItemDeleted(Message):
        def __init__(self, path: str) -> None:
            super().__init__()
            self.path = path

    class NewRequest(Message):
        """User wants a blank new request."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("Collection", **kwargs)
        self._pending_delete: str | None = None

    def on_mount(self) -> None:
        self.root.expand()
        self.guide_depth = 3

    def load_collection(self, items: dict[str, list[dict]]) -> None:
        self.root.remove_children()
        icons = {"uac": "\u260e", "flows": "\u25b6"}
        for category, entries in items.items():
            icon = icons.get(category, "\u2022")
            node = self.root.add(f"{icon} {category.upper()}", expand=True)
            for entry in entries:
                node.add_leaf(entry["name"], data=entry)

    def action_delete_item(self) -> None:
        node = self.cursor_node
        if node is None or not isinstance(node.data, dict):
            return
        path = node.data.get("path", "")
        if not path:
            return
        if self._pending_delete == path:
            self.post_message(self.ItemDeleted(path))
            self._pending_delete = None
        else:
            self._pending_delete = path
            self.app.notify(
                f"Press Delete again to confirm: {path.rsplit('/', 1)[-1]}",
                severity="warning",
            )

    def action_new_request(self) -> None:
        self.post_message(self.NewRequest())


# ── Flow panel ──────────────────────────────────────────────────────────────


class FlowPanel(Container):
    """Flow YAML editor + execution log + progress."""

    BINDINGS = [
        Binding("c", "copy_log", "Copy Log", show=False),
    ]

    running: reactive[bool] = reactive(False)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._flow_path: str = ""
        self._log_lines: list[str] = []

    def compose(self) -> ComposeResult:
        editor_box = Vertical(id="flow-editor-section")
        editor_box.border_title = "Flow"
        with editor_box:
            yield TextArea(language="yaml", theme="monokai", id="flow-editor")

        with Horizontal(id="flow-toolbar"):
            yield Button("\u25b6 Run", id="flow-run-btn")
            yield Button("Save", id="flow-save-btn")
            yield Button("Copy Log", id="flow-copy-btn")
            yield ProgressBar(id="flow-progress", total=100, show_eta=False)

        log_box = Vertical(id="flow-log-section")
        log_box.border_title = "Execution Log"
        with log_box:
            yield RichLog(id="flow-log", markup=True, auto_scroll=True)

    def load_flow(self, yaml_text: str, path: str = "") -> None:
        self._flow_path = path
        self.query_one("#flow-editor", TextArea).load_text(yaml_text)
        name = path.rsplit("/", 1)[-1] if path else "new flow"
        self.query_one("#flow-editor-section").border_title = f"Flow: {name}"

    def get_yaml(self) -> str:
        return self.query_one("#flow-editor", TextArea).text

    @property
    def flow_path(self) -> str:
        return self._flow_path

    def log(self, text: str) -> None:
        self._log_lines.append(text)
        self.query_one("#flow-log", RichLog).write(text)

    def set_progress(self, current: int, total: int) -> None:
        self.query_one("#flow-progress", ProgressBar).update(
            total=total, progress=current
        )

    @on(Button.Pressed, "#flow-copy-btn")
    def _on_copy_log(self) -> None:
        self.action_copy_log()

    def action_copy_log(self) -> None:
        """Copy execution log to clipboard."""
        import re

        clean = "\n".join(re.sub(r"\[.*?\]", "", line) for line in self._log_lines)
        self.app.copy_to_clipboard(clean)
        self.app.notify("Flow log copied to clipboard")


# ── Log panel (global bottom drawer) ──────────────────────────────────────


class LogPanel(Vertical):
    """Global log panel — toggleable bottom drawer showing all activity."""

    def compose(self) -> ComposeResult:
        yield Label("Log", id="log-panel-title")
        yield RichLog(id="global-log", markup=True, auto_scroll=True)

    def log(self, text: str) -> None:
        """Write a log entry."""
        try:
            self.query_one("#global-log", RichLog).write(text)
        except Exception:
            pass

    def clear(self) -> None:
        """Clear all log entries."""
        try:
            self.query_one("#global-log", RichLog).clear()
        except Exception:
            pass


# ── Status bar with sparkline ───────────────────────────────────────────────


class StatusBar(Horizontal):
    """Bottom status bar with capture stats and packet rate sparkline."""

    packets: reactive[int] = reactive(0)
    dialogs: reactive[int] = reactive(0)
    mode: reactive[str] = reactive("ready")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._rate_history: list[float] = [0] * 20
        self._last_count: int = 0

    def compose(self) -> ComposeResult:
        yield Static("", id="status-text")
        yield Sparkline(self._rate_history, id="status-sparkline")

    def update_rate(self, current_count: int) -> None:
        """Track packet rate (packets since last tick)."""
        delta = current_count - self._last_count
        self._last_count = current_count
        self._rate_history.append(float(delta))
        if len(self._rate_history) > 20:
            self._rate_history.pop(0)
        try:
            self.query_one("#status-sparkline", Sparkline).data = list(
                self._rate_history
            )
        except Exception:
            pass

    def watch_packets(self) -> None:
        self._update_text()

    def watch_dialogs(self) -> None:
        self._update_text()

    def watch_mode(self) -> None:
        self._update_text()

    def _update_text(self) -> None:
        try:
            self.query_one("#status-text", Static).update(
                f" Pkts: {self.packets}"
                f"  \u2502  Dlgs: {self.dialogs}"
                f"  \u2502  {self.mode}"
            )
        except Exception:
            pass
