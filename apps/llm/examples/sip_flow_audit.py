from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from sipx_harness import Harness, Verdict, scenario
from sipx_llm import LLMChatClient


SAMPLE_TRACE = """
SIP RX 203.0.113.20:5060
SIP/2.0 401 Unauthorized
WWW-Authenticate: Digest realm="pbx.example.com", nonce="n1", qop="auth"
CSeq: 1 REGISTER

SIP TX 203.0.113.20:5060
REGISTER sip:pbx.example.com SIP/2.0
Authorization: [REDACTED]
CSeq: 2 REGISTER

SIP RX 203.0.113.20:5060
SIP/2.0 200 OK
CSeq: 2 REGISTER

SIP TX 203.0.113.20:5060
INVITE sip:ivr@example.com SIP/2.0
Content-Type: application/sdp
CSeq: 1 INVITE

v=0
m=audio 41000 RTP/AVP 0 8 101
a=rtpmap:0 PCMU/8000
a=rtpmap:101 telephone-event/8000

SIP RX 203.0.113.20:5060
SIP/2.0 180 Ringing
CSeq: 1 INVITE

SIP RX 203.0.113.20:5060
SIP/2.0 200 OK
Content-Type: application/sdp
CSeq: 1 INVITE

v=0
m=audio 52000 RTP/AVP 0 101
a=rtpmap:0 PCMU/8000
a=rtpmap:101 telephone-event/8000

SIP TX 203.0.113.20:5060
ACK sip:ivr@example.com SIP/2.0
CSeq: 1 ACK

SIP TX 203.0.113.20:5060
INFO sip:ivr@example.com SIP/2.0
Content-Type: application/dtmf-relay
CSeq: 2 INFO

Signal=1
Duration=160

SIP RX 203.0.113.20:5060
SIP/2.0 200 OK
CSeq: 2 INFO

SIP TX 203.0.113.20:5060
BYE sip:ivr@example.com SIP/2.0
CSeq: 3 BYE

SIP RX 203.0.113.20:5060
SIP/2.0 200 OK
CSeq: 3 BYE
""".strip()


@scenario("sip_flow_audit", provider="openai-compatible")
async def scenario(h: Harness) -> Verdict:
    trace = _load_trace_from_env()
    result = await audit_trace(trace)
    h.timeline.record("llm", "sip_flow_audit", data=result)
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] == "skipped":
        return Verdict.skipped(reason=str(result["reason"]))
    if result["deterministic"]["critical_findings"]:
        return Verdict.failed(reason="deterministic SIP audit found critical issues")
    return Verdict.passed(reason="SIP flow audit completed")


async def audit_trace(trace: str) -> dict[str, Any]:
    deterministic = _deterministic_audit(trace)
    if not os.getenv("SIPX_LLM_API_KEY"):
        return {
            "status": "skipped",
            "reason": "SIPX_LLM_API_KEY not set",
            "deterministic": deterministic,
        }

    client = LLMChatClient.from_env()
    prompt = _audit_prompt(trace, deterministic)
    raw = await client.complete(
        prompt,
        system=(
            "You audit SIP call flows. Return strict JSON only. "
            "Do not include markdown fences. Do not include secrets."
        ),
        max_tokens=1200,
    )
    llm = _parse_json_object(raw)
    return {
        "status": "completed",
        "deterministic": deterministic,
        "llm": llm,
    }


def _load_trace_from_env() -> str:
    path = os.getenv("SIPX_LLM_TRACE_FILE")
    if path:
        return Path(path).read_text(encoding="utf-8")
    return SAMPLE_TRACE


def _deterministic_audit(trace: str) -> dict[str, Any]:
    upper = trace.upper()
    critical: list[str] = []
    warnings: list[str] = []
    signals = {
        "register_digest_challenge": "401 UNAUTHORIZED" in upper
        and "REGISTER" in upper,
        "invite_has_sdp_offer": "INVITE " in upper
        and "CONTENT-TYPE: APPLICATION/SDP" in upper
        and "M=AUDIO" in upper,
        "dtmf_info": "INFO " in upper and "APPLICATION/DTMF-RELAY" in upper,
        "clean_bye": "BYE " in upper and "CSEQ: 3 BYE" in upper and "200 OK" in upper,
    }
    if "INVITE " in upper and "SIP/2.0 200 OK" in upper:
        invite_ok_index = upper.find("SIP/2.0 200 OK", upper.find("INVITE "))
        invite_answer_window = upper[invite_ok_index : invite_ok_index + 500]
        if "CONTENT-TYPE: APPLICATION/SDP" not in invite_answer_window:
            critical.append("INVITE reached 200 OK without an SDP answer nearby")
    for line in trace.splitlines():
        normalized = line.strip().upper()
        if (
            normalized.startswith(("AUTHORIZATION:", "PROXY-AUTHORIZATION:"))
            and "[REDACTED]" not in normalized
        ):
            critical.append("trace contains an unredacted authorization header")
            break
    if "APPLICATION/DTMF-RELAY" in upper and "DURATION=" not in upper:
        warnings.append("DTMF relay body has no Duration field")
    return {
        "signals": signals,
        "critical_findings": critical,
        "warnings": warnings,
    }


def _audit_prompt(trace: str, deterministic: dict[str, Any]) -> str:
    return json.dumps(
        {
            "task": "Audit this SIP flow for interoperability and behavior.",
            "required_json_shape": {
                "summary": "one paragraph",
                "behavior": "accepted|rejected|incomplete|unknown",
                "risk_score": "integer 0-100",
                "protocol_findings": [
                    {
                        "severity": "info|warning|critical",
                        "evidence": "quote from trace",
                        "meaning": "what it implies",
                        "recommendation": "what to do next",
                    }
                ],
                "media_assessment": {
                    "sdp": "short assessment",
                    "dtmf": "short assessment",
                    "rtp_readiness": "short assessment",
                },
                "next_actions": ["ordered actions"],
            },
            "deterministic_signals": deterministic,
            "sip_trace": trace,
        },
        indent=2,
    )


def _parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end < start:
        raise ValueError("LLM response did not contain a JSON object")
    value = json.loads(stripped[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("LLM response JSON must be an object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit a SIP trace with an LLM.")
    parser.add_argument(
        "--trace-file",
        help="Path to a text SIP trace. Defaults to the embedded healthy sample.",
    )
    args = parser.parse_args(argv)

    if args.trace_file:
        os.environ["SIPX_LLM_TRACE_FILE"] = args.trace_file
    verdict = asyncio.run(Harness().run(scenario))
    reason = f": {verdict.reason}" if verdict.reason else ""
    print(f"{verdict.status}{reason}")
    return 0 if verdict.status in {"passed", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
