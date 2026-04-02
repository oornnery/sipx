"""Main SipxApp — Textual application for sipx TUI.

Three tabs: Request | Flows | Capture
Global log panel (bottom drawer).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Select,
    TabPane,
)

from ._capture import CapturedPacket, Direction, PacketStore
from ._collection import CollectionManager, SipProfile
from ._flows import Flow, FlowRunner
from ._styles import APP_CSS
from ._transport import InterceptingTransport
from ._widgets import (
    CollectionTree,
    FlowPanel,
    HeaderEditor,
    LogPanel,
    MethodBar,
    PacketTable,
    RequestSection,
    ResponseSection,
    SipLadder,
    SipxTabs,
    StatusBar,
)


class SipxApp(App):
    """sipx — Interactive SIP Workbench & Packet Analyzer."""

    TITLE = "sipx"
    SUB_TITLE = "SIP Workbench"
    CSS = APP_CSS

    BINDINGS = [
        Binding("ctrl+j", "send", "Send", show=True, priority=True),
        Binding("ctrl+h", "toggle_sidebar", "Sidebar", show=True),
        Binding("ctrl+r", "run_flow", "Run Flow", show=True),
        Binding("ctrl+s", "save_profile", "Save", show=True),
        Binding("ctrl+l", "clear_capture", "Clear", show=True),
        Binding("ctrl+f", "toggle_flow", "Flows", show=True),
        Binding("ctrl+g", "toggle_log", "Log", show=True),
        Binding("ctrl+m", "toggle_expand", "Expand", show=False),
        Binding("escape", "back", "Back", show=False),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._store = PacketStore()
        self._collection = CollectionManager()
        self._client: Any = None
        self._server: Any = None
        self._refresh_timer: Any = None
        self._active_profile: SipProfile | None = None
        self._expanded: str | None = None
        self._capture_detail_open: bool = False

    # ── Compose ────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="workspace"):
            with Vertical(id="sidebar"):
                yield Label("Collection", id="sidebar-title")
                yield CollectionTree(id="collection-tree")

            with SipxTabs(id="main-tabs"):
                # ── Request tab ──
                with TabPane("Request", id="tab-request"):
                    req_box = Vertical(id="request-section")
                    req_box.border_title = "Request"
                    with req_box:
                        yield MethodBar(id="method-bar")
                        yield RequestSection(id="request-editor")

                    resp_box = Horizontal(id="response-section")
                    resp_box.border_title = "Response"
                    with resp_box:
                        yield SipLadder(self._store, id="req-ladder")
                        yield ResponseSection(id="req-response")

                # ── Flows tab ──
                with TabPane("Flows", id="tab-flows"):
                    yield FlowPanel(id="flow-panel")

                # ── Capture tab (two pages) ──
                with TabPane("Capture", id="tab-capture"):
                    # Page 1: Dialog list
                    cap_list = Vertical(id="capture-list-page")
                    cap_list.border_title = "Capture"
                    with cap_list:
                        yield PacketTable(self._store, id="packet-table")

                    # Page 2: Dialog detail (hidden by default)
                    cap_detail = Vertical(id="capture-detail-page", classes="hidden")
                    cap_detail.border_title = "Detail"
                    with cap_detail:
                        with Horizontal(id="capture-detail-bar"):
                            yield Button("\u2190 Back", id="capture-back-btn")
                            yield Label("", id="capture-detail-title")
                        with Horizontal(id="capture-detail-content"):
                            yield SipLadder(self._store, id="cap-ladder")
                            with SipxTabs(id="capture-right-tabs"):
                                with TabPane("Raw", id="cap-tab-raw"):
                                    yield RichLog(id="cap-raw-view", markup=True)
                                with TabPane("Detail", id="cap-tab-detail"):
                                    yield RichLog(id="cap-detail-view", markup=True)

        yield LogPanel(id="log-panel", classes="hidden")
        yield StatusBar(id="status-bar")
        yield Footer()

    # ── Lifecycle ──────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self._collection.ensure_dirs()
        self._reload_collection()
        self._refresh_timer = self.set_interval(0.1, self._tick)

    def _tick(self) -> None:
        try:
            table = self.query_one("#packet-table", PacketTable)
            table.refresh_packets()
        except Exception:
            pass
        sb = self.query_one("#status-bar", StatusBar)
        sb.packets = len(self._store)
        sb.dialogs = len(self._store.call_ids)
        sb.update_rate(len(self._store))

    @on(SipxTabs.TabActivated)
    def _on_tab_changed(self, event: SipxTabs.TabActivated) -> None:
        """Force-refresh PacketTable when switching to Capture tab."""
        if event.pane and getattr(event.pane, "id", None) == "tab-capture":
            try:
                table = self.query_one("#packet-table", PacketTable)
                table._pkt_count = 0  # Force full rebuild
                table._rebuild()
                # Debug: show store state
                n_pkts = len(self._store)
                n_dlgs = len(self._store.call_ids)
                self.notify(
                    f"Store: {n_pkts} pkts, {n_dlgs} dialogs",
                    severity="information",
                )
            except Exception as exc:
                self.notify(f"Rebuild error: {exc}", severity="error")

    def _reload_collection(self) -> None:
        self.query_one("#collection-tree", CollectionTree).load_collection(
            self._collection.list_items()
        )

    # ── Section expand/collapse ─────────────────────────────────────

    def action_toggle_expand(self) -> None:
        """Cycle: both -> request only -> response only -> both."""
        req = self.query_one("#request-section")
        resp = self.query_one("#response-section")
        if self._expanded is None:
            resp.display = False
            self._expanded = "request"
        elif self._expanded == "request":
            req.display = False
            resp.display = True
            self._expanded = "response"
        else:
            req.display = True
            resp.display = True
            self._expanded = None

    # ── Logging (global log panel) ─────────────────────────────────

    def _log(self, text: str) -> None:
        """Log to the global log panel."""
        try:
            self.query_one("#log-panel", LogPanel).log(text)
        except Exception:
            pass

    # ── Transport tap ───────────────────────────────────────────────

    def _on_transport_send(self, data: bytes, dest: Any) -> None:
        if not data:
            return
        local = getattr(self._client, "local_address", None)
        self._store.add(
            CapturedPacket.from_raw(
                data,
                Direction.SENT,
                local.host if local else "0.0.0.0",
                local.port if local else 0,
                dest.host,
                dest.port,
                local.protocol if local else "UDP",
            )
        )

    def _on_transport_recv(self, data: bytes, source: Any) -> None:
        if not data:
            return
        local = getattr(self._client, "local_address", None)
        self._store.add(
            CapturedPacket.from_raw(
                data,
                Direction.RECV,
                source.host,
                source.port,
                local.host if local else "0.0.0.0",
                local.port if local else 0,
                local.protocol if local else "UDP",
            )
        )

    def _wrap_client_transport(self, client: Any) -> None:
        self._client = client
        client._transport = InterceptingTransport(
            client._transport,
            on_send=self._on_transport_send,
            on_recv=self._on_transport_recv,
        )

    def capture_sent(
        self,
        raw: bytes,
        dst_host: str,
        dst_port: int,
        src_host: str = "0.0.0.0",
        src_port: int = 0,
        protocol: str = "UDP",
    ) -> None:
        if raw:
            self._store.add(
                CapturedPacket.from_raw(
                    raw,
                    Direction.SENT,
                    src_host,
                    src_port,
                    dst_host,
                    dst_port,
                    protocol,
                )
            )

    def capture_recv(
        self,
        raw: bytes,
        src_host: str,
        src_port: int,
        dst_host: str = "0.0.0.0",
        dst_port: int = 0,
        protocol: str = "UDP",
    ) -> None:
        if raw:
            self._store.add(
                CapturedPacket.from_raw(
                    raw,
                    Direction.RECV,
                    src_host,
                    src_port,
                    dst_host,
                    dst_port,
                    protocol,
                )
            )

    # ── Fallback capture ─────────────────────────────────────────────

    def _ensure_captured(self, resp: Any, client: Any) -> None:
        """Ensure request/response packets are in the store."""
        call_id = resp.headers.get("Call-ID", "")
        if not call_id:
            return
        if self._store.get_dialog(call_id):
            return

        local = getattr(client, "local_address", None)
        info = getattr(resp, "transport_info", {})
        protocol = info.get("protocol", "UDP")
        src_host = local.host if local else "0.0.0.0"
        src_port = local.port if local else 0

        remote = info.get("remote", "")
        dst_host, dst_port = "0.0.0.0", 5060
        if remote:
            parts = remote.rsplit(":", 2)
            if len(parts) >= 3:
                dst_host, dst_port = parts[1], int(parts[2])
            elif len(parts) == 2:
                dst_host, dst_port = parts[0], int(parts[1])

        req = getattr(resp, "request", None)
        if req:
            try:
                self.capture_sent(
                    req.to_bytes(),
                    dst_host,
                    dst_port,
                    src_host,
                    src_port,
                    protocol,
                )
            except Exception:
                pass

        raw = getattr(resp, "raw", None)
        if raw:
            try:
                self.capture_recv(
                    raw,
                    dst_host,
                    dst_port,
                    src_host,
                    src_port,
                    protocol,
                )
            except Exception:
                pass

    # ── Request tab: update response view ──────────────────────────

    def _update_request_response(self, call_id: str) -> None:
        """Update the Request tab's ladder and response section."""
        if not call_id:
            return
        try:
            ladder = self.query_one("#req-ladder", SipLadder)
            ladder.show_dialog(call_id, force=True)
            # Show last packet in response view
            dialog = self._store.get_dialog(call_id)
            if dialog:
                last = dialog[-1]
                self.query_one("#req-response", ResponseSection).show_packet(
                    last, self._store
                )
        except Exception:
            pass

    # ── Capture detail page ────────────────────────────────────────

    def _open_capture_detail(self, call_id: str) -> None:
        """Switch capture tab from list page to detail page."""
        self._capture_detail_open = True
        self.query_one("#capture-list-page").add_class("hidden")
        detail = self.query_one("#capture-detail-page")
        detail.remove_class("hidden")

        # Update title
        dialog = self._store.get_dialog(call_id)
        title = ""
        if dialog:
            first = dialog[0]
            method = first.method or "???"
            title = f"{method}  {first.src} \u2192 {first.dst}  ({len(dialog)} msgs)"
        self.query_one("#capture-detail-title", Label).update(title)
        detail.border_title = f"Detail \u2014 {title}"

        # Show ladder
        ladder = self.query_one("#cap-ladder", SipLadder)
        ladder.show_dialog(call_id, force=True)

        # Show first packet raw
        if dialog:
            self._show_capture_packet(dialog[0])

    def _close_capture_detail(self) -> None:
        """Return from detail page to list page."""
        self._capture_detail_open = False
        self.query_one("#capture-detail-page").add_class("hidden")
        self.query_one("#capture-list-page").remove_class("hidden")

    def _show_capture_packet(self, pkt: CapturedPacket) -> None:
        """Update capture detail raw/detail views."""
        from ._ladder import render_packet_detail

        # Update border title
        elapsed = self._store.elapsed(pkt)
        det = self.query_one("#capture-detail-page")
        det.border_title = (
            f"Detail \u2014 {pkt.direction.value} {pkt.summary} "
            f"{pkt.src} \u2192 {pkt.dst} ({elapsed:.3f}s)"
        )

        # Raw view (sngrep-style syntax highlight)
        from ._widgets import write_sip_raw

        write_sip_raw(self.query_one("#cap-raw-view", RichLog), pkt, self._store)

        # Detail view
        detail_view = self.query_one("#cap-detail-view", RichLog)
        detail_view.clear()
        detail_view.write(render_packet_detail(pkt, self._store))

    # ── Event handlers ──────────────────────────────────────────────

    @on(SipLadder.PacketSelected)
    def _on_ladder_packet(self, event: SipLadder.PacketSelected) -> None:
        """Ladder click — route to request or capture detail."""
        if not (0 <= event.index < len(self._store.packets)):
            return
        pkt = self._store.packets[event.index]
        # Determine which ladder sent this by walking ancestors
        sender = event._sender
        is_capture = False
        widget = sender
        while widget is not None:
            if getattr(widget, "id", None) == "capture-detail-page":
                is_capture = True
                break
            widget = widget.parent
        if is_capture:
            self._show_capture_packet(pkt)
        else:
            self.query_one("#req-response", ResponseSection).show_packet(
                pkt, self._store
            )

    @on(PacketTable.DialogOpened)
    def _on_dialog_opened(self, event: PacketTable.DialogOpened) -> None:
        """Dialog node clicked in capture list -> open detail page."""
        self._open_capture_detail(event.call_id)

    @on(PacketTable.PacketSelected)
    def _on_packet_selected(self, event: PacketTable.PacketSelected) -> None:
        """Packet leaf clicked in capture list -> open detail + select."""
        if 0 <= event.index < len(self._store.packets):
            pkt = self._store.packets[event.index]
            if pkt.call_id:
                self._open_capture_detail(pkt.call_id)
                self._show_capture_packet(pkt)

    @on(Button.Pressed, "#capture-back-btn")
    def _on_capture_back(self) -> None:
        self._close_capture_detail()

    @on(MethodBar.SendPressed)
    def _on_send_pressed(self) -> None:
        self.action_send()

    @on(MethodBar.NewCallIdPressed)
    def _on_new_callid(self) -> None:
        """Regenerate Call-ID in header editor."""
        try:
            editor = self.query_one("#header-editor", HeaderEditor)
            editor.regenerate_call_id()
            # Clear the request ladder
            self.query_one("#req-ladder", SipLadder).clear()
            self.query_one("#req-response", ResponseSection).clear()
            self.query_one(MethodBar).clear_status()
            self.notify("New Call-ID generated")
        except Exception:
            pass

    @on(Button.Pressed, "#flow-run-btn")
    def _on_flow_run(self) -> None:
        self.action_run_flow()

    @on(Button.Pressed, "#flow-save-btn")
    def _on_flow_save(self) -> None:
        self._save_flow()

    @on(MethodBar.RequestChanged)
    def _on_request_changed(self, event: MethodBar.RequestChanged) -> None:
        try:
            self.query_one("#header-editor", HeaderEditor).populate_from_uri(
                event.method, event.uri
            )
        except Exception:
            pass

    @on(CollectionTree.ItemDeleted)
    def _on_collection_delete(self, event: CollectionTree.ItemDeleted) -> None:
        if self._collection.delete_profile(event.path):
            self._reload_collection()
            self.notify(f"Deleted: {event.path.rsplit('/', 1)[-1]}")

    @on(CollectionTree.NewRequest)
    def _on_new_request(self) -> None:
        tabs = self.query_one("#main-tabs", SipxTabs)
        tabs.active = "tab-request"
        self.query_one("#method-select", Select).value = "INVITE"
        self.query_one("#uri-input", Input).value = ""
        method_bar = self.query_one(MethodBar)
        method_bar.clear_status()
        self.query_one("#req-ladder", SipLadder).clear()
        self.query_one("#req-response", ResponseSection).clear()
        self.query_one("#uri-input", Input).focus()

    @on(CollectionTree.NodeSelected, "#collection-tree")
    def _on_collection_item(self, event: Any) -> None:
        node = event.node
        if node.data and isinstance(node.data, dict):
            path = node.data.get("path", "")
            if not path:
                return
            if "/flows/" in path:
                yaml_text = self._collection.load_flow_yaml(path)
                if yaml_text:
                    self._show_flow_panel(yaml_text, path=path)
            else:
                profile = self._collection.load_profile(path)
                if profile:
                    self._load_profile(profile)

    def _load_profile(self, profile: SipProfile) -> None:
        self._active_profile = profile
        self.query_one("#main-tabs", SipxTabs).active = "tab-request"
        self.query_one("#method-select", Select).value = profile.method
        self.query_one("#uri-input", Input).value = profile.uri
        if profile.auth_user:
            self.query_one("#auth-user", Input).value = profile.auth_user
            self.query_one("#auth-pass", Input).value = profile.auth_pass
        self.query_one(MethodBar).clear_status()
        self.query_one("#status-bar", StatusBar).mode = f"profile: {profile.name}"

    def _show_flow_panel(self, yaml_text: str, path: str = "") -> None:
        self.query_one("#main-tabs", SipxTabs).active = "tab-flows"
        self.query_one("#flow-panel", FlowPanel).load_flow(yaml_text, path=path)
        self.query_one("#status-bar", StatusBar).mode = "flow"

    # ── Actions ─────────────────────────────────────────────────────

    def action_toggle_sidebar(self) -> None:
        self.query_one("#sidebar").toggle_class("hidden")

    def action_toggle_flow(self) -> None:
        tabs = self.query_one("#main-tabs", SipxTabs)
        if tabs.active == "tab-flows":
            tabs.active = "tab-request"
            self.query_one("#status-bar", StatusBar).mode = "ready"
        else:
            tabs.active = "tab-flows"
            self.query_one("#status-bar", StatusBar).mode = "flow"

    def action_toggle_log(self) -> None:
        """Toggle the global log panel."""
        self.query_one("#log-panel", LogPanel).toggle_class("hidden")

    def action_back(self) -> None:
        """Escape — close capture detail or log panel."""
        if self._capture_detail_open:
            self._close_capture_detail()
        elif not self.query_one("#log-panel").has_class("hidden"):
            self.query_one("#log-panel").add_class("hidden")

    def action_clear_capture(self) -> None:
        self._store.clear()
        try:
            table = self.query_one("#packet-table", PacketTable)
            table._pkt_count = 0
            table._rebuild()
        except Exception:
            pass
        # Also clear capture detail if open
        if self._capture_detail_open:
            self._close_capture_detail()

    def _get_compose_data(self) -> tuple[str, str, dict[str, str], str, str, str]:
        method = str(self.query_one("#method-select", Select).value or "INVITE")
        uri = self.query_one("#uri-input", Input).value
        req = self.query_one(RequestSection)
        return method, uri, req.get_headers(), req.get_body(), *req.get_auth()

    @work(exclusive=True, thread=False)
    async def action_send(self) -> None:
        method, uri, headers, body, auth_user, auth_pass = self._get_compose_data()
        if not uri:
            self.notify("Enter a SIP URI first", severity="error")
            return

        send_btn = self.query_one("#send-button", Button)
        send_btn.disabled = True
        method_bar = self.query_one(MethodBar)
        method_bar.clear_error()
        method_bar.clear_status()

        sb = self.query_one("#status-bar", StatusBar)
        sb.mode = "sending..."

        # Get Call-ID for updating the request ladder after send
        call_id = headers.get("Call-ID", "")

        self._log(f"[cyan]\u25b6 {method} {uri}[/cyan]")

        t0 = time.monotonic()

        try:
            from ..client import AsyncClient
            from ..models._auth import SipAuthCredentials
            from .._types import TimeoutError as SipTimeout
            from .._types import TransportError

            auth = None
            if auth_user and auth_pass:
                auth = SipAuthCredentials(username=auth_user, password=auth_pass)

            async with AsyncClient(auth=auth) as client:
                self._wrap_client_transport(client)

                kwargs: dict[str, Any] = {}
                if headers:
                    kwargs["headers"] = headers
                if body:
                    kwargs["content"] = body

                method_fn = getattr(client, method.lower(), None)
                if method_fn is None:
                    self.notify(f"Unknown method: {method}", severity="error")
                    return

                if method.upper() in ("INVITE", "BYE"):
                    kwargs["to_uri"] = uri
                elif method.upper() == "REGISTER":
                    kwargs["aor"] = uri
                else:
                    kwargs["uri"] = uri

                resp = await method_fn(**kwargs)
                elapsed_ms = (time.monotonic() - t0) * 1000

                if resp:
                    self._ensure_captured(resp, client)

                    # Update response Call-ID (may differ from request)
                    resp_call_id = resp.headers.get("Call-ID", call_id)

                    self._log(
                        f"[green]\u25c0 {resp.status_code} "
                        f"{resp.reason_phrase} ({elapsed_ms:.1f}ms)[/green]"
                    )
                    method_bar.show_status(
                        resp.status_code, resp.reason_phrase, elapsed_ms
                    )

                    # Update Request tab response section
                    self.query_one("#response-section").border_title = (
                        f"Response \u2014 {resp.status_code} "
                        f"{resp.reason_phrase} ({elapsed_ms:.1f}ms)"
                    )
                    self._update_request_response(resp_call_id)
                else:
                    elapsed_ms = (time.monotonic() - t0) * 1000
                    self.query_one(
                        "#response-section"
                    ).border_title = f"Response \u2014 timeout ({elapsed_ms:.0f}ms)"
                    self._log(f"[red]No response ({elapsed_ms:.0f}ms)[/red]")
                    method_bar.show_error("timeout")
                    self.notify("No response (timeout)", severity="error")

        except SipTimeout as exc:
            method_bar.show_error("timeout")
            self._log(f"[red]Timeout: {exc}[/red]")
            self.notify(f"Timeout: {exc}", severity="error")
        except TransportError as exc:
            method_bar.show_error("error")
            self._log(f"[red]Transport error: {exc}[/red]")
            self.notify(f"Transport: {exc}", severity="error")
        except Exception as exc:
            method_bar.show_error("error")
            self._log(f"[red]Error: {exc}[/red]")
            self.notify(f"Send failed: {exc}", severity="error")
        finally:
            self._client = None
            send_btn.disabled = False
            sb.mode = "ready"

    def _save_flow(self) -> None:
        flow_panel = self.query_one("#flow-panel", FlowPanel)
        yaml_text = flow_panel.get_yaml()
        if not yaml_text.strip():
            self.notify("Flow editor is empty", severity="error")
            return

        from pathlib import Path

        path = flow_panel.flow_path
        if path:
            Path(path).write_text(yaml_text)
            self.notify(f"Saved: {path}", severity="information")
        else:
            self._collection.ensure_dirs()
            fp = self._collection.base_dir / "flows" / "new-flow.yaml"
            fp.write_text(yaml_text)
            flow_panel._flow_path = str(fp)
            self.notify(f"Saved: {fp}", severity="information")
        self._reload_collection()

    @work(exclusive=True, thread=False)
    async def action_run_flow(self) -> None:
        flow_panel = self.query_one("#flow-panel", FlowPanel)
        yaml_text = flow_panel.get_yaml()
        if not yaml_text.strip():
            self.notify("Flow editor is empty", severity="error")
            return

        try:
            flow = Flow.parse(yaml_text)
        except Exception as exc:
            self.notify(f"Invalid flow YAML: {exc}", severity="error")
            return

        sb = self.query_one("#status-bar", StatusBar)
        sb.mode = f"flow: {flow.name}"
        flow_panel.running = True
        total_steps = len(flow.steps) or len(flow.on_invite)

        def on_step_start(i: int, step: Any) -> None:
            flow_panel.set_progress(i, total_steps)

        def on_step_done(i: int, result: Any) -> None:
            flow_panel.set_progress(i + 1, total_steps)
            icon = "\u2713" if result.status.value == "success" else "\u2717"
            msg = f"  {icon} Step {i + 1}: {result.message}"
            flow_panel.log(msg)
            self._log(msg)

        def flow_log(text: str) -> None:
            flow_panel.log(text)
            self._log(text)

        runner = FlowRunner(
            flow,
            on_step_start=on_step_start,
            on_step_done=on_step_done,
            on_log=flow_log,
        )

        try:
            from ..client import AsyncClient

            async with AsyncClient() as client:
                self._wrap_client_transport(client)
                await runner.run(client=client)
        except Exception as exc:
            flow_panel.log(f"[red]Flow error: {exc}[/red]")
            self._log(f"[red]Flow error: {exc}[/red]")
            self.notify(f"Flow failed: {exc}", severity="error")
        finally:
            self._client = None
            flow_panel.running = False
            sb.mode = "ready"

    def action_save_profile(self) -> None:
        method, uri, headers, body, auth_user, auth_pass = self._get_compose_data()
        name = "new-profile"
        if uri:
            bare = uri
            if bare.startswith(("sip:", "sips:")):
                bare = bare.split(":", 1)[1]
            name = bare.split(";")[0].split("?")[0]

        profile = SipProfile(
            name=name,
            category="uac",
            uri=uri,
            method=method,
            auth_user=auth_user,
            auth_pass=auth_pass,
            headers=headers,
            body=body,
        )
        path = self._collection.save_profile(profile)
        self._reload_collection()
        self.notify(f"Saved: {path}", severity="information")

    # ── Listen mode ─────────────────────────────────────────────────

    @work(exclusive=True, thread=False)
    async def start_listener(
        self,
        host: str = "0.0.0.0",
        port: int = 5060,
        protocol: str = "UDP",
    ) -> None:
        from ..server import AsyncSIPServer

        sb = self.query_one("#status-bar", StatusBar)
        sb.mode = f"listening {host}:{port}"
        self.query_one("#main-tabs", SipxTabs).active = "tab-capture"

        server = AsyncSIPServer(local_host=host, local_port=port)

        def _make_handler(method: str) -> None:
            @server.handle(method)
            def _handler(request: Any, source: Any) -> Any:
                self.capture_recv(
                    request.to_bytes(),
                    source.host,
                    source.port,
                    host,
                    port,
                    protocol,
                )
                resp = request.ok()
                self.capture_sent(
                    resp.to_bytes(),
                    host,
                    port,
                    source.host,
                    source.port,
                    protocol,
                )
                return resp

        for m in [
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
        ]:
            _make_handler(m)

        try:
            await server.start()
            self._server = server
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await server.stop()
            self._server = None
            sb.mode = "ready"
