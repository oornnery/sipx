# sip_ladder.py
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Group
from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.events import MouseUp
from textual.message import Message
from textual.reactive import reactive
from textual.scroll_view import ScrollView
from textual.widgets import Header, Static


@dataclass
class SipEvent:
    time: str
    src: str
    dst: str
    method: str
    info: str = ""
    raw: Optional[str] = None


TIME_COLUMN_WIDTH = 24
MIN_COLUMN_WIDTH = 18
COLUMN_GAP = 6


def _layout(actors: List[str]) -> Tuple[Dict[str, int], Dict[str, int], int, int]:
    if not actors:
        return {}, {}, TIME_COLUMN_WIDTH, MIN_COLUMN_WIDTH

    col_width = max(MIN_COLUMN_WIDTH, max(len(a) for a in actors) + 8)
    centers: Dict[str, int] = {}
    starts: Dict[str, int] = {}

    for index, actor in enumerate(actors):
        start = TIME_COLUMN_WIDTH + index * (col_width + COLUMN_GAP)
        starts[actor] = start
        centers[actor] = start + max(2, col_width // 2)

    total_width = TIME_COLUMN_WIDTH + len(actors) * (col_width + COLUMN_GAP)
    return centers, starts, total_width, col_width


def _base_row(total_width: int, centers: Dict[str, int]) -> List[str]:
    row = [" "] * total_width
    for x in centers.values():
        if 0 <= x < total_width:
            row[x] = "│"
    return row


def _format_time_label(value: str) -> str:
    label = value.strip()
    return label.ljust(TIME_COLUMN_WIDTH)


def _format_delta_label(delta: Optional[float]) -> str:
    if delta is None:
        return "".ljust(TIME_COLUMN_WIDTH)
    label = f"+{delta:.6f}"
    return label.ljust(TIME_COLUMN_WIDTH)


def _parse_time(value: str) -> Optional[datetime]:
    candidates = ("%H:%M:%S.%f", "%H:%M:%S")
    for fmt in candidates:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _method_style(method: str) -> Style:
    label = method.upper().strip()
    if not label:
        return Style(color="white", bold=True)

    if label.startswith("RTP"):
        return Style(color="#00bcd4", bold=True)

    first = label[0]
    if first.isdigit():
        try:
            status = int(label.split()[0])
        except ValueError:
            status = 0
        if 100 <= status < 200:
            return Style(color="#d7af00", bold=True)
        if 200 <= status < 300:
            return Style(color="#4caf50", bold=True)
        if 300 <= status < 400:
            return Style(color="#ff00ff", bold=True)
        return Style(color="#d70000", bold=True)

    return Style(color="#ff0000", bold=True)


def _sip_body(raw: Optional[str]) -> str:
    if not raw:
        return ""
    split = raw.split("\r\n\r\n", 1)
    if len(split) == 1:
        split = raw.split("\n\n", 1)
    if len(split) == 2:
        return split[1].strip()
    return ""


def _has_sdp(event: SipEvent) -> bool:
    info_flag = event.info.upper().find("SDP") != -1 if event.info else False
    raw_flag = event.raw.lower().find("application/sdp") != -1 if event.raw else False
    body_flag = "v=0" in _sip_body(event.raw)
    return info_flag or raw_flag or body_flag


def _is_dtmf(event: SipEvent) -> bool:
    if event.info and "dtmf" in event.info.lower():
        return True
    if event.raw:
        raw_lower = event.raw.lower()
        if "telephone-event" in raw_lower:
            return True
        for line in event.raw.splitlines():
            if line.lower().startswith("signal=") or line.lower().startswith("event="):
                return True
    return False


def _is_rtp(event: SipEvent) -> bool:
    if event.method.upper().startswith("RTP"):
        return True
    if event.info and "rtp" in event.info.lower():
        return True
    if event.raw and "RTP/" in event.raw.upper():
        return True
    return False


def _sdp_summary(raw: Optional[str]) -> Optional[str]:
    body = _sip_body(raw)
    if not body or "v=0" not in body:
        return None
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    media_line = next((line for line in lines if line.startswith("m=")), None)
    conn_line = next((line for line in lines if line.startswith("c=")), None)
    if not media_line:
        return None
    media_parts = media_line.split()
    if len(media_parts) < 4:
        return media_line
    media_type = media_parts[0][2:]
    port = media_parts[1]
    proto = media_parts[2]
    payloads = ",".join(media_parts[3:])
    summary = f"SDP {media_type}:{port} {proto} [{payloads}]"
    if conn_line:
        conn_parts = conn_line.split()
        if len(conn_parts) >= 3:
            summary += f" @{conn_parts[-1]}"
    return summary


def _dtmf_summary(event: SipEvent) -> Optional[str]:
    if event.info and "dtmf" in event.info.lower():
        return event.info.strip()
    if event.raw:
        for line in event.raw.splitlines():
            lower = line.lower()
            if lower.startswith("signal="):
                return f"DTMF signal {line.split('=', 1)[1].strip()}"
            if lower.startswith("event="):
                return f"DTMF event {line.split('=', 1)[1].strip()}"
    return None


def _rtp_summary(event: SipEvent) -> Optional[str]:
    if event.info and event.info.lower().startswith("rtp"):
        return event.info.strip()
    body = _sip_body(event.raw)
    if body:
        for line in body.splitlines():
            lower = line.lower().strip()
            if lower.startswith("m=audio"):
                parts = line.split()
                if len(parts) >= 4:
                    payloads = ",".join(parts[3:])
                    return f"RTP audio/{parts[1]} [{payloads}]"
            if lower.startswith("m=video"):
                parts = line.split()
                if len(parts) >= 4:
                    payloads = ",".join(parts[3:])
                    return f"RTP video/{parts[1]} [{payloads}]"
    if event.raw and "RTP/" in event.raw.upper():
        return "RTP stream"
    return None


def _event_badges(event: SipEvent) -> str:
    badges: List[str] = []
    if _has_sdp(event):
        badges.append("SDP")
    if _is_dtmf(event):
        badges.append("DTMF")
    if _is_rtp(event):
        badges.append("RTP")
    if (
        event.info
        and event.info.strip()
        and event.info.strip().upper() not in {"SDP", "DTMF"}
    ):
        badges.append(event.info.strip())
    return "[" + " | ".join(badges) + "]" if badges else ""


def _event_summary(event: SipEvent) -> str:
    details: List[str] = []
    sdp_info = _sdp_summary(event.raw)
    if sdp_info:
        details.append(sdp_info)
    dtmf_info = _dtmf_summary(event)
    if dtmf_info:
        details.append(dtmf_info)
    rtp_info = _rtp_summary(event)
    if rtp_info:
        details.append(rtp_info)
    info = event.info.strip() if event.info else ""
    if info and info.upper() not in {"SDP", "DTMF"}:
        details.append(info)
    return " • ".join(details)


class LadderSelected(Message):
    BUBBLE = True

    def __init__(self, event: SipEvent, index: int) -> None:
        self.event = event
        self.index = index
        super().__init__()


class LadderWidget(Static):
    can_focus = True
    BINDINGS = [
        ("up", "cursor_up", "Evento anterior"),
        ("down", "cursor_down", "Próximo evento"),
    ]

    selected: int = reactive(0)

    def __init__(
        self, actors: List[str], events: List[SipEvent], **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self.actors = actors
        self.events = events
        self._line_ranges: List[Tuple[int, int]] = []

    @staticmethod
    def _render_ladder(
        actors: List[str],
        events: List[SipEvent],
        selected_index: Optional[int] = None,
    ) -> Tuple[Text, List[Tuple[int, int]]]:
        centers, starts, total_width, col_width = _layout(actors)

        lifeline_style = Style(color="#747474")
        arrow_style = Style(color="#00bcd4")
        time_style = Style(color="#b0b0b0")
        delta_style = Style(color="#888888")
        info_style = Style(color="#ffd75f")
        highlight_style = Style(bgcolor="#303030")
        dtmf_style = Style(color="#ff8700", bold=True)
        rtp_style = Style(color="#7cff00", bold=True)

        lines: List[Text] = []
        line_ranges: List[Tuple[int, int]] = []
        line_no = 0

        if not actors:
            empty = Text("No actors", style=Style(color="#808080"))
            empty.append("\n")
            return empty, []

        top = [" "] * total_width
        mid = [" "] * total_width
        bottom = [" "] * total_width

        for actor in actors:
            start = starts[actor]
            end = min(total_width - 1, start + col_width - 1)
            if start >= total_width:
                continue
            top[start] = "┌"
            bottom[start] = "└"
            for idx in range(start + 1, end):
                top[idx] = bottom[idx] = "─"
            if end < total_width:
                top[end] = "┐"
                bottom[end] = "┘"
            mid[start] = "│"
            if end < total_width:
                mid[end] = "│"
            label = actor
            label_start = start + max(1, (col_width - len(label)) // 2)
            for offset, char in enumerate(label):
                pos = label_start + offset
                if pos < end:
                    mid[pos] = char

        lines.append(Text("".join(top), style=Style(color="#b0b0b0")))
        line_no += 1
        lines.append(Text("".join(mid), style=Style(color="#e0e0e0", bold=True)))
        line_no += 1
        lines.append(Text("".join(bottom), style=Style(color="#b0b0b0")))
        line_no += 1

        header_row = _base_row(total_width, centers)
        header_text = Text("".join(header_row))
        for x in centers.values():
            header_text.stylize(lifeline_style, x, x + 1)
        lines.append(header_text)
        line_no += 1

        previous_time: Optional[str] = None
        previous_dt: Optional[datetime] = None

        for idx, event in enumerate(events):
            start_line = line_no

            base_row = _base_row(total_width, centers)
            arrow_row = base_row[:]

            time_label = _format_time_label(event.time)
            for offset, char in enumerate(time_label[:TIME_COLUMN_WIDTH]):
                arrow_row[offset] = char

            x1 = centers.get(event.src)
            x2 = centers.get(event.dst)

            dtmf_event = _is_dtmf(event)
            rtp_event = _is_rtp(event)

            summary = _event_summary(event)
            if summary:
                info_row = _base_row(total_width, centers)
                summary_label = summary
                for offset, char in enumerate(
                    summary_label[: total_width - TIME_COLUMN_WIDTH]
                ):
                    pos = TIME_COLUMN_WIDTH + offset
                    if pos < total_width:
                        info_row[pos] = char
                info_text = Text("".join(info_row))
                info_end = TIME_COLUMN_WIDTH + len(summary_label)
                info_text.stylize(
                    info_style, TIME_COLUMN_WIDTH, min(info_end, total_width)
                )
                for x in centers.values():
                    if 0 <= x < len(info_text):
                        info_text.stylize(lifeline_style, x, x + 1)
                lines.append(info_text)
                line_no += 1

            if x1 is not None and x2 is not None:
                start = min(x1, x2)
                end = max(x1, x2)
                arrow_row[x1] = "●"
                if x1 <= x2:
                    arrow_row[end] = "▶"
                else:
                    arrow_row[start] = "◀"
                for column in range(start + 1, end):
                    arrow_row[column] = "─"

                label_text = event.method.strip() or "(?)"
                badge_text = _event_badges(event)
                if badge_text:
                    label_text = f"{label_text} {badge_text}"
                label_length = len(label_text)
                span = max(1, end - start)
                label_start = max(
                    TIME_COLUMN_WIDTH, start + 1 + max(0, (span - label_length) // 2)
                )
                label_start = min(
                    label_start, max(TIME_COLUMN_WIDTH, total_width - label_length - 1)
                )
                for offset, char in enumerate(label_text):
                    pos = label_start + offset
                    if TIME_COLUMN_WIDTH <= pos < total_width:
                        arrow_row[pos] = char

            arrow_text = Text("".join(arrow_row))
            arrow_text.stylize(time_style, 0, TIME_COLUMN_WIDTH)
            for x in centers.values():
                if 0 <= x < len(arrow_text):
                    arrow_text.stylize(lifeline_style, x, x + 1)

            if x1 is not None and x2 is not None:
                segment_start = max(TIME_COLUMN_WIDTH, min(x1, x2))
                segment_end = min(total_width, max(x1, x2) + 1)
                segment_style = (
                    dtmf_style
                    if dtmf_event
                    else rtp_style
                    if rtp_event
                    else arrow_style
                )
                arrow_text.stylize(segment_style, segment_start, segment_end)

                label_text = event.method.strip() or "(?)"
                badge_text = _event_badges(event)
                if badge_text:
                    label_text = f"{label_text} {badge_text}"
                label_index = arrow_text.plain.find(label_text, TIME_COLUMN_WIDTH)
                if label_index != -1:
                    method_style = (
                        dtmf_style
                        if dtmf_event
                        else rtp_style
                        if rtp_event
                        else _method_style(event.method)
                    )
                    arrow_text.stylize(
                        method_style, label_index, label_index + len(label_text)
                    )

            lines.append(arrow_text)
            line_no += 1

            delta_row = _base_row(total_width, centers)
            current_dt = _parse_time(event.time)
            delta_value = None
            if previous_dt and current_dt:
                delta = (current_dt - previous_dt).total_seconds()
                if delta < 0 and previous_time is not None:
                    delta = 0.0
                delta_value = delta
            delta_label = _format_delta_label(delta_value)
            for offset, char in enumerate(delta_label[:TIME_COLUMN_WIDTH]):
                delta_row[offset] = char
            delta_text = Text("".join(delta_row))
            delta_text.stylize(delta_style, 0, TIME_COLUMN_WIDTH)
            for x in centers.values():
                if 0 <= x < len(delta_text):
                    delta_text.stylize(lifeline_style, x, x + 1)
            lines.append(delta_text)
            line_no += 1

            end_line = line_no - 1
            line_ranges.append((start_line, end_line))

            previous_time = event.time
            previous_dt = current_dt or previous_dt

        trailer = _base_row(total_width, centers)
        trailer_text = Text("".join(trailer))
        for x in centers.values():
            trailer_text.stylize(lifeline_style, x, x + 1)
        lines.append(trailer_text)

        if selected_index is not None and 0 <= selected_index < len(line_ranges):
            sel_start, sel_end = line_ranges[selected_index]
            for idx in range(sel_start, sel_end + 1):
                if 0 <= idx < len(lines):
                    lines[idx].stylize(highlight_style, 0, len(lines[idx]))

        rendered = Text()
        for line in lines:
            rendered.append(line)
            rendered.append("\n")
        return rendered, line_ranges

    def watch_selected(self, old: int, new: int) -> None:  # noqa: ARG002
        if not self.events:
            self.refresh()
            return
        clamped = max(0, min(new, len(self.events) - 1))
        if clamped != new:
            self.selected = clamped
            return
        self.post_message(LadderSelected(self.events[clamped], clamped))
        self.refresh()

    def on_mount(self) -> None:
        if self.events:
            self.selected = max(0, min(self.selected, len(self.events) - 1))
            self.post_message(LadderSelected(self.events[self.selected], self.selected))

    def render(self) -> Text:
        selected_index = self.selected if self.events else None
        text, ranges = self._render_ladder(self.actors, self.events, selected_index)
        self._line_ranges = ranges
        return text

    def _select(self, index: int) -> None:
        if not self.events:
            return
        index = max(0, min(index, len(self.events) - 1))
        if index != self.selected:
            self.selected = index
            self.refresh()
        else:
            self.post_message(LadderSelected(self.events[index], index))
            self.refresh()

    def action_cursor_up(self) -> None:
        self._select(self.selected - 1)

    def action_cursor_down(self) -> None:
        self._select(self.selected + 1)

    def on_mouse_up(self, event: MouseUp) -> None:
        line = max(0, int(event.y))
        for idx, (start, end) in enumerate(self._line_ranges):
            if start <= line <= end:
                self._select(idx)
                event.stop()
                return


def render_ladder(
    actors: List[str],
    events: List[SipEvent],
    selected_index: Optional[int] = None,
) -> Tuple[Text, List[Tuple[int, int]]]:
    return LadderWidget._render_ladder(actors, events, selected_index)


class DetailPanel(ScrollView):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._event: Optional[SipEvent] = None
        self._content = Static(expand=True)

    def compose(self) -> ComposeResult:
        yield self._content

    def on_mount(self) -> None:
        self.border_title = "Detalhes"
        self.styles.border = ("solid", "#5a5a5a")
        self.styles.padding = (1, 2)
        self.show_message("Selecione uma transação para ver detalhes")

    def show_message(self, message: str) -> None:
        self._event = None
        self._content.update(Text(message, style="#949494"))
        self.scroll_home()

    def show_event(self, event: SipEvent) -> None:
        self._event = event
        self._content.update(_event_detail_renderable(event))
        self.scroll_home()


def _sip_headers(raw: Optional[str]) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if not raw:
        return headers
    lines = raw.splitlines()
    for line in lines[1:]:
        if not line.strip():
            break
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip()] = value.strip()
    return headers


def _event_detail_renderable(event: SipEvent) -> Group:
    header = Text()
    header.append(
        f"{event.method.upper()} ",
        style=Style(color="#00bcd4", bold=True),
    )
    header.append(f"{event.src} → {event.dst}\n", style=Style(color="white"))
    header.append(f"Horário: {event.time}\n", style="#b0b0b0")

    headers = _sip_headers(event.raw)
    for key in ("Call-ID", "CSeq", "Content-Type", "Contact"):
        if key in headers:
            header.append(f"{key}: {headers[key]}\n", style="#9e9e9e")

    badges = _event_badges(event)
    if badges:
        header.append(f"Etiquetas: {badges}\n", style=Style(color="#d7af00"))

    sdp_info = _sdp_summary(event.raw)
    if sdp_info:
        header.append(f"{sdp_info}\n", style=Style(color="#00bcd4"))

    dtmf_info = _dtmf_summary(event)
    if dtmf_info:
        header.append(f"{dtmf_info}\n", style=Style(color="#ff8700"))
    rtp_info = _rtp_summary(event)
    if rtp_info:
        header.append(f"{rtp_info}\n", style=Style(color="#7cff00"))

    sections: List[Any] = [header]

    if event.raw:
        syntax = Syntax(event.raw, "text", theme="ansi_dark", line_numbers=False)
        sections.append(syntax)
    else:
        sections.append(Text("Sem payload bruto", style="#808080"))

    return Group(*sections)


class SIPLadder(Container):
    DEFAULT_CSS = """
    SIPLadder {
        layout: horizontal;
        height: 1fr;
        width: 1fr;
    }
    SIPLadder > .ladder {
        width: 3fr;
        overflow-y: auto;
        padding: 1 0 1 0;
    }
    SIPLadder > .detail {
        width: 4fr;
        overflow-y: auto;
        border: none;
        padding: 0;
    }
    """

    def __init__(
        self, actors: List[str], events: List[SipEvent], **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self._actors = actors
        self._events = events
        self._ladder = LadderWidget(actors, events, classes="ladder")
        self._detail = DetailPanel(classes="detail")

    def compose(self) -> ComposeResult:
        yield self._ladder
        yield self._detail

    def on_mount(self) -> None:
        self.focus_ladder()

    def focus_ladder(self) -> None:
        if self._ladder:
            self._ladder.focus()

    def on_ladder_selected(self, message: LadderSelected) -> None:
        self._detail.show_event(message.event)


class SipLadderApp(App):
    CSS = """
    Screen {
        layout: vertical;
    }
    """

    def __init__(self, data: Dict[str, Any]):
        super().__init__()
        self._data = data
        self._sipladder: Optional[SIPLadder] = None

    def compose(self) -> ComposeResult:
        actors: List[str] = self._data.get("actors", [])
        events = [SipEvent(**e) for e in self._data.get("events", [])]
        self._sipladder = SIPLadder(actors, events)
        yield Header()
        yield self._sipladder

    def on_mount(self) -> None:
        if self._sipladder:
            self._sipladder.focus_ladder()


def load_data(path: str | None) -> Dict[str, Any]:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))

    return {
        "actors": [
            "192.168.56.1:5060",
            "192.168.11.102:5060",
            "192.168.11.115:5065",
        ],
        "events": [
            {
                "time": "15:36:42.463690",
                "src": "192.168.56.1:5060",
                "dst": "192.168.11.102:5060",
                "method": "INVITE",
                "info": "SDP",
                "raw": (
                    "INVITE sip:100@192.168.56.101 SIP/2.0\r\n"
                    "Via: SIP/2.0/UDP 192.168.56.1:5060;branch=z9hG4bK-1234\r\n"
                    'From: "Phone A" <sip:100@192.168.56.1>;tag=9f47a\r\n'
                    "To: <sip:100@192.168.56.101>\r\n"
                    "Call-ID: 00BE3708-805D-EB11-A91D-2F392F4E5BD8@192.168.56.1_in2out\r\n"
                    "CSeq: 1 INVITE\r\n"
                    "Contact: <sip:100@192.168.56.1:5060>\r\n"
                    "Max-Forwards: 69\r\n"
                    "Content-Type: application/sdp\r\n"
                    "Content-Length: 215\r\n"
                    "\r\n"
                    "v=0\r\n"
                    "o=phonerlite 2 2 IN IP4 192.168.56.1\r\n"
                    "s=PhonerLite 2.82\r\n"
                    "c=IN IP4 192.168.11.102\r\n"
                    "t=0 0\r\n"
                    "m=audio 1038 RTP/AVP 0 3 8 9 18 101\r\n"
                    "a=rtpmap:0 PCMU/8000\r\n"
                    "a=rtpmap:3 GSM/8000\r\n"
                    "a=rtpmap:8 PCMA/8000\r\n"
                    "a=rtpmap:9 G722/8000\r\n"
                    "a=rtpmap:18 G729/8000\r\n"
                    "a=rtpmap:101 telephone-event/8000\r\n"
                    "a=fmtp:101 0-16\r\n"
                    "a=sendrecv\r\n"
                ),
            },
            {
                "time": "15:36:42.470215",
                "src": "192.168.11.102:5060",
                "dst": "192.168.56.1:5060",
                "method": "100 Trying",
                "info": "",
            },
            {
                "time": "15:36:42.478402",
                "src": "192.168.11.102:5060",
                "dst": "192.168.56.1:5060",
                "method": "200 OK",
                "info": "SDP",
                "raw": (
                    "SIP/2.0 200 OK\r\n"
                    "Via: SIP/2.0/UDP 192.168.56.1:5060;branch=z9hG4bK-1234\r\n"
                    'From: "Phone A" <sip:100@192.168.56.1>;tag=9f47a\r\n'
                    "To: <sip:100@192.168.56.101>;tag=281d3\r\n"
                    "Call-ID: 00BE3708-805D-EB11-A91D-2F392F4E5BD8@192.168.56.1_in2out\r\n"
                    "CSeq: 1 INVITE\r\n"
                    "Contact: <sip:100@192.168.11.102:5060>\r\n"
                    "Content-Type: application/sdp\r\n"
                    "Content-Length: 205\r\n"
                    "\r\n"
                    "v=0\r\n"
                    "o=b2bua 385 386 IN IP4 192.168.11.102\r\n"
                    "s=phone-call\r\n"
                    "c=IN IP4 192.168.11.102\r\n"
                    "t=0 0\r\n"
                    "m=audio 11500 RTP/AVP 0 8 18 101\r\n"
                    "a=rtpmap:0 PCMU/8000\r\n"
                    "a=rtpmap:8 PCMA/8000\r\n"
                    "a=rtpmap:18 G729/8000\r\n"
                    "a=rtpmap:101 telephone-event/8000\r\n"
                    "a=fmtp:101 0-16\r\n"
                    "a=sendrecv\r\n"
                ),
            },
            {
                "time": "15:36:42.480048",
                "src": "192.168.56.1:5060",
                "dst": "192.168.11.102:5060",
                "method": "ACK",
                "info": "",
                "raw": (
                    "ACK sip:100@192.168.11.102:5060 SIP/2.0\r\n"
                    "Via: SIP/2.0/UDP 192.168.56.1:5060;branch=z9hG4bK-1234\r\n"
                    'From: "Phone A" <sip:100@192.168.56.1>;tag=9f47a\r\n'
                    "To: <sip:100@192.168.56.101>;tag=281d3\r\n"
                    "Call-ID: 00BE3708-805D-EB11-A91D-2F392F4E5BD8@192.168.56.1_in2out\r\n"
                    "CSeq: 1 ACK\r\n"
                    "Contact: <sip:100@192.168.56.1:5060>\r\n"
                    "Max-Forwards: 69\r\n"
                    "Content-Length: 0\r\n"
                    "\r\n"
                ),
            },
            {
                "time": "15:36:43.345192",
                "src": "192.168.56.1:5060",
                "dst": "192.168.11.102:5060",
                "method": "INFO",
                "info": "DTMF 5",
                "raw": (
                    "INFO sip:100@192.168.11.102:5060 SIP/2.0\r\n"
                    "Via: SIP/2.0/UDP 192.168.56.1:5060;branch=z9hG4bK-5678\r\n"
                    'From: "Phone A" <sip:100@192.168.56.1>;tag=9f47a\r\n'
                    "To: <sip:100@192.168.56.101>;tag=281d3\r\n"
                    "Call-ID: 00BE3708-805D-EB11-A91D-2F392F4E5BD8@192.168.56.1_in2out\r\n"
                    "CSeq: 2 INFO\r\n"
                    "Contact: <sip:100@192.168.56.1:5060>\r\n"
                    "Max-Forwards: 69\r\n"
                    "Content-Type: application/dtmf-relay\r\n"
                    "Content-Length: 18\r\n"
                    "\r\n"
                    "Signal=5\r\n"
                    "Duration=160\r\n"
                ),
            },
            {
                "time": "15:36:43.348081",
                "src": "192.168.11.102:5060",
                "dst": "192.168.56.1:5060",
                "method": "200 OK",
                "info": "INFO",
                "raw": (
                    "SIP/2.0 200 OK\r\n"
                    "Via: SIP/2.0/UDP 192.168.56.1:5060;branch=z9hG4bK-5678\r\n"
                    'From: "Phone A" <sip:100@192.168.56.1>;tag=9f47a\r\n'
                    "To: <sip:100@192.168.56.101>;tag=281d3\r\n"
                    "Call-ID: 00BE3708-805D-EB11-A91D-2F392F4E5BD8@192.168.56.1_in2out\r\n"
                    "CSeq: 2 INFO\r\n"
                    "Content-Length: 0\r\n"
                    "\r\n"
                ),
            },
            {
                "time": "15:37:04.426413",
                "src": "192.168.56.1:5060",
                "dst": "192.168.11.102:5060",
                "method": "BYE",
                "info": "",
                "raw": (
                    "BYE sip:100@192.168.11.102:5060 SIP/2.0\r\n"
                    "Via: SIP/2.0/UDP 192.168.56.1:5060;branch=z9hG4bK-9abc\r\n"
                    'From: "Phone A" <sip:100@192.168.56.1>;tag=9f47a\r\n'
                    "To: <sip:100@192.168.56.101>;tag=281d3\r\n"
                    "Call-ID: 00BE3708-805D-EB11-A91D-2F392F4E5BD8@192.168.56.1_in2out\r\n"
                    "CSeq: 3 BYE\r\n"
                    "Max-Forwards: 69\r\n"
                    "Content-Length: 0\r\n"
                    "\r\n"
                ),
            },
            {
                "time": "15:37:04.427187",
                "src": "192.168.11.102:5060",
                "dst": "192.168.56.1:5060",
                "method": "200 OK",
                "info": "BYE",
                "raw": (
                    "SIP/2.0 200 OK\r\n"
                    "Via: SIP/2.0/UDP 192.168.56.1:5060;branch=z9hG4bK-9abc\r\n"
                    'From: "Phone A" <sip:100@192.168.56.1>;tag=9f47a\r\n'
                    "To: <sip:100@192.168.56.101>;tag=281d3\r\n"
                    "Call-ID: 00BE3708-805D-EB11-A91D-2F392F4E5BD8@192.168.56.1_in2out\r\n"
                    "CSeq: 3 BYE\r\n"
                    "Content-Length: 0\r\n"
                    "\r\n"
                ),
            },
        ],
    }


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    data = load_data(path)
    SipLadderApp(data).run()
