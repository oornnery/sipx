"""SIP Ladder diagram renderer — sngrep/Wireshark-style call flow."""

from __future__ import annotations

from rich.table import Table
from rich.text import Text

from ._capture import CapturedPacket, Direction, PacketStore


def _status_color(pkt: CapturedPacket) -> str:
    """Return Rich color name based on packet type."""
    if pkt.method:
        return "cyan bold"
    if pkt.status_code < 200:
        return "dim"
    if pkt.status_code < 300:
        return "green bold"
    if pkt.status_code < 400:
        return "yellow"
    return "red bold"


def _arrow(direction: Direction, width: int = 20) -> tuple[str, str]:
    """Return (left_pad, arrow) for the given direction and width."""
    line = "\u2500" * (width - 2)
    if direction == Direction.SENT:
        return "", f"{line}\u25b6"
    return "", f"\u25c0{line}"


def render_ladder(
    packets: list[CapturedPacket],
    store: PacketStore,
    selected: CapturedPacket | None = None,
) -> Table:
    """Render a SIP ladder diagram as a Rich Table.

    ```
    Time      Source              Message              Destination
    0.001s    10.0.0.1:5060    ──── INVITE ────▶     192.168.1.1:5060
    0.010s    192.168.1.1:5060 ◀── 100 Trying ───   10.0.0.1:5060
    0.050s    192.168.1.1:5060 ◀── 200 OK ────────   10.0.0.1:5060
    0.051s    10.0.0.1:5060    ──── ACK ──────▶      192.168.1.1:5060
    ```
    """
    if not packets:
        table = Table(show_header=False, box=None, padding=0)
        table.add_row(Text("No packets in this dialog", style="dim italic"))
        return table

    # Collect unique endpoints
    endpoints: list[str] = []
    seen: set[str] = set()
    for pkt in packets:
        for ep in (pkt.src, pkt.dst):
            if ep not in seen:
                seen.add(ep)
                endpoints.append(ep)

    # Build header with endpoint names as columns
    table = Table(
        show_header=True,
        header_style="bold",
        box=None,
        padding=(0, 1),
        expand=True,
    )
    table.add_column("Time", style="dim", width=10, no_wrap=True)

    if len(endpoints) == 2:
        # Two-column ladder (most common: client ↔ server)
        left, right = endpoints[0], endpoints[1]
        table.add_column(left, width=22, no_wrap=True)
        table.add_column("", ratio=1)  # Arrow column
        table.add_column(right, width=22, no_wrap=True)

        for pkt in packets:
            elapsed = store.elapsed(pkt)
            color = _status_color(pkt)
            label = pkt.summary
            is_selected = pkt is selected

            # Determine arrow direction
            if pkt.src == left:
                # Left → Right
                arrow_text = Text()
                arrow_text.append("\u2500" * 4, style=color)
                arrow_text.append(f" {label} ", style=color)
                arrow_text.append("\u2500" * 4 + "\u25b6", style=color)

                left_mark = Text("\u2502", style="dim")
                right_mark = Text("\u2502", style="dim")
            else:
                # Right → Left
                arrow_text = Text()
                arrow_text.append("\u25c0" + "\u2500" * 4, style=color)
                arrow_text.append(f" {label} ", style=color)
                arrow_text.append("\u2500" * 4, style=color)

                left_mark = Text("\u2502", style="dim")
                right_mark = Text("\u2502", style="dim")

            time_text = Text(f"{elapsed:.3f}s", style="bold" if is_selected else "dim")

            if is_selected:
                arrow_text.stylize("reverse")

            table.add_row(time_text, left_mark, arrow_text, right_mark)
    else:
        # Multi-endpoint or single — fall back to source/arrow/dest columns
        table.add_column("Source", width=22, no_wrap=True)
        table.add_column("", ratio=1)
        table.add_column("Destination", width=22, no_wrap=True)

        for pkt in packets:
            elapsed = store.elapsed(pkt)
            color = _status_color(pkt)
            label = pkt.summary
            is_selected = pkt is selected

            if pkt.direction == Direction.SENT:
                arrow = Text(f"\u2500\u2500 {label} \u2500\u25b6", style=color)
            else:
                arrow = Text(f"\u25c0\u2500 {label} \u2500\u2500", style=color)

            time_text = Text(f"{elapsed:.3f}s", style="bold" if is_selected else "dim")
            src = Text(pkt.src, style="cyan" if is_selected else "")
            dst = Text(pkt.dst, style="cyan" if is_selected else "")

            if is_selected:
                arrow.stylize("reverse")

            table.add_row(time_text, src, arrow, dst)

    return table


def render_packet_detail(pkt: CapturedPacket, store: PacketStore) -> Table:
    """Render Wireshark-style packet detail — protocol tree view.

    ```
    Session Initiation Protocol (OPTIONS)
    ├── Request-Line: OPTIONS sip:bob@192.168.1.1 SIP/2.0
    ├── Via: SIP/2.0/UDP 10.0.0.1:5060;branch=z9hG4bK...
    ├── From: <sip:alice@10.0.0.1>;tag=abc123
    ├── To: <sip:bob@192.168.1.1>
    ├── Call-ID: test123@10.0.0.1
    ├── CSeq: 1 OPTIONS
    ├── Max-Forwards: 70
    ├── Content-Length: 0
    └── [Message Body: 0 bytes]
    ```
    """
    table = Table(
        show_header=False,
        box=None,
        padding=(0, 0),
        expand=True,
    )
    table.add_column("", ratio=1)

    # Title line
    summary = pkt.summary
    proto = pkt.protocol
    elapsed = store.elapsed(pkt)

    title = Text()
    title.append(f"Session Initiation Protocol ({summary})", style="bold cyan")
    table.add_row(title)

    # Meta info
    meta_lines = [
        (
            "Direction",
            pkt.direction.value
            + " "
            + ("Sent" if pkt.direction == Direction.SENT else "Received"),
        ),
        ("Source", pkt.src),
        ("Destination", pkt.dst),
        ("Protocol", proto),
        ("Size", f"{pkt.size} bytes"),
        ("Time", f"{elapsed:.6f}s"),
    ]

    for key, val in meta_lines:
        line = Text()
        line.append("\u251c\u2500\u2500 ", style="dim")
        line.append(f"{key}: ", style="bold")
        line.append(val)
        table.add_row(line)

    # Parse headers from raw
    text = pkt.decoded
    lines = text.replace("\r\n", "\n").split("\n")

    if lines:
        # Start line
        start = Text()
        start.append("\u251c\u2500\u2500 ", style="dim")
        if pkt.method:
            start.append("Request-Line: ", style="bold yellow")
        else:
            start.append("Status-Line: ", style="bold green")
        start.append(lines[0])
        table.add_row(start)

    # Headers
    header_lines = []
    body_start = len(lines)
    for i, line in enumerate(lines[1:], 1):
        if not line:
            body_start = i + 1
            break
        if ":" in line:
            header_lines.append(line)

    for i, hdr in enumerate(header_lines):
        name, _, val = hdr.partition(":")
        is_last_header = (i == len(header_lines) - 1) and body_start >= len(lines)
        prefix = "\u2514\u2500\u2500 " if is_last_header else "\u251c\u2500\u2500 "

        line = Text()
        line.append(prefix, style="dim")
        line.append(f"{name.strip()}: ", style="bold")
        line.append(val.strip())
        table.add_row(line)

    # Body info
    body_bytes = 0
    if body_start < len(lines):
        body_text = "\n".join(lines[body_start:])
        body_bytes = len(body_text.encode("utf-8"))

    body_line = Text()
    body_line.append("\u2514\u2500\u2500 ", style="dim")
    if body_bytes > 0:
        body_line.append(f"[Message Body: {body_bytes} bytes]", style="italic")
    else:
        body_line.append("[No Message Body]", style="dim italic")
    table.add_row(body_line)

    return table
