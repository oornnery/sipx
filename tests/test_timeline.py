import json

from sipx import Timeline, TimelineEvent


def test_timeline_records_monotonic_correlated_events() -> None:
    timeline = Timeline(run_id="run-1", clock_ns=lambda: 10)

    first = timeline.record(
        "sip",
        "tx",
        actor_id="caller",
        call_id="call-1",
        leg_id="leg-1",
    )
    second = timeline.record("sip", "rx", actor_id="caller", call_id="call-1")

    assert first.ts_ns == 10
    assert second.ts_ns == 11
    assert second.call_id == "call-1"


def test_timeline_jsonl_round_trip() -> None:
    event = TimelineEvent(
        ts_ns=1,
        run_id="run-1",
        actor_id="actor-1",
        call_id="call-1",
        leg_id="leg-1",
        category="rtp",
        name="rx",
        data={"packets": 1},
    )

    restored = TimelineEvent.from_dict(json.loads(json.dumps(event.to_dict())))

    assert restored == event
