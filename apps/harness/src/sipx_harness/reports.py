from __future__ import annotations

from html import escape

from sipx_harness.artifacts import Artifact, ArtifactKind, ArtifactStore
from sipx_harness.timeline import Timeline
from sipx_harness.verdict import Verdict


def render_text_report(timeline: Timeline, verdict: Verdict) -> str:
    lines = [
        f"sipx report: {timeline.run_id}",
        f"status: {verdict.status}",
    ]
    if verdict.reason:
        lines.append(f"reason: {verdict.reason}")
    if verdict.metrics:
        lines.append(f"metrics: {verdict.metrics}")
    lines.append("events:")
    for event in timeline.events:
        actor = f" actor={event.actor_id}" if event.actor_id else ""
        call = f" call={event.call_id}" if event.call_id else ""
        lines.append(
            f"- {event.ts_ns} {event.category}.{event.name}{actor}{call} {event.data}"
        )
    return "\n".join(lines) + "\n"


def render_html_report(timeline: Timeline, verdict: Verdict) -> str:
    rows = []
    for event in timeline.events:
        rows.append(
            "<tr>"
            f"<td>{event.ts_ns}</td>"
            f"<td>{escape(event.category)}</td>"
            f"<td>{escape(event.name)}</td>"
            f"<td>{escape(event.actor_id or '')}</td>"
            f"<td>{escape(event.call_id or '')}</td>"
            f"<td><code>{escape(str(event.data))}</code></td>"
            "</tr>"
        )
    reason = (
        f"<p><strong>Reason:</strong> {escape(verdict.reason)}</p>"
        if verdict.reason
        else ""
    )
    return (
        "<!doctype html>\n"
        '<html><head><meta charset="utf-8"><title>sipx report</title>'
        "<style>body{font-family:sans-serif;max-width:1100px;margin:2rem}"
        "table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:.4rem}"
        "code{white-space:pre-wrap}</style></head><body>"
        f"<h1>sipx report: {escape(timeline.run_id)}</h1>"
        f"<p><strong>Status:</strong> {escape(verdict.status)}</p>"
        f"{reason}"
        "<h2>Timeline</h2><table>"
        "<thead><tr><th>ts_ns</th><th>category</th><th>name</th>"
        "<th>actor</th><th>call</th><th>data</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
        "</body></html>\n"
    )


def write_report_artifacts(
    store: ArtifactStore,
    timeline: Timeline,
    verdict: Verdict,
) -> tuple[Artifact, Artifact]:
    text = store.write_text(
        "report.txt",
        render_text_report(timeline, verdict),
        kind=ArtifactKind.REPORT,
        metadata={"format": "text"},
    )
    html = store.write_text(
        "report.html",
        render_html_report(timeline, verdict),
        kind=ArtifactKind.REPORT,
        metadata={"format": "html"},
    )
    return text, html
