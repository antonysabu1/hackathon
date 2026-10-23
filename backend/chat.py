"""Coach chat. The LLM only sees computed findings, never raw telemetry.

If ANTHROPIC_API_KEY is missing or the call fails, a rule-based answer is
returned so the demo never breaks.
"""
import json
import os
import re

SYSTEM = """You are a sim racing coach inside a telemetry app.
You are given structured findings computed from the driver's lap compared to a reference lap.
Rules:
- Use only the numbers in the findings. Never invent telemetry values.
- Explain in plain words for someone who is not an expert. Keep answers under 140 words.
- Check driver inputs before blaming the car setup. If the findings say the setup is the suspect,
  suggest ONE change at a time and tell them to run about 8 clean laps to verify.
- Be honest about uncertainty. These are estimates.
- Do not use dashes as punctuation. Use commas or full stops instead."""


def _compact(analysis: dict) -> str:
    data = {
        "summary": analysis["summary"],
        "corners": [
            {k: c[k] for k in ("name", "time_loss", "you", "ref", "issues", "snap")}
            for c in analysis["corners"]
        ],
    }
    return json.dumps(data, separators=(",", ":"))


def _fallback(analysis: dict, message: str) -> str:
    m = message.lower()
    corners = analysis["corners"]
    by_name = {c["name"].lower(): c for c in corners}
    mt = re.search(r"\bt\s?(\d+)\b", m)
    c = by_name.get(f"t{mt.group(1)}") if mt else None

    def describe(c):
        if not c["issues"]:
            return f"{c['name']} looks clean. You lost {c['time_loss']:.2f} s there, which is within normal noise."
        parts = [f"{c['name']} cost you {c['time_loss']:.2f} s."]
        for i in c["issues"][:2]:
            parts.append(i["message"])
        parts.append("Next lap: " + c["issues"][0]["fix"])
        return " ".join(parts)

    if c:
        return describe(c)
    snaps = [x for x in corners if x["snap"]]
    if any(w in m for w in ("snap", "spin", "oversteer", "setup", "car")) and snaps:
        return describe(snaps[0])
    worst = [x for x in sorted(corners, key=lambda x: x["time_loss"], reverse=True) if x["issues"]][:3]
    if not worst:
        return "I do not see any clear mistakes against this reference lap."
    return analysis["summary"]["headline"] + " Biggest losses: " + " ".join(
        f"{x['name']} ({x['time_loss']:.2f} s): {x['issues'][0]['message']}" for x in worst)


def reply(analysis: dict, message: str, history: list) -> dict:
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return {"text": _fallback(analysis, message), "source": "offline"}
    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=key)
        msgs = []
        for h in history[-6:]:
            if h.get("role") in ("user", "assistant") and h.get("text"):
                msgs.append({"role": h["role"], "content": h["text"]})
        msgs.append({"role": "user", "content": message})
        resp = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
            max_tokens=500,
            system=SYSTEM + "\n\nFINDINGS (JSON):\n" + _compact(analysis),
            messages=msgs,
        )
        return {"text": "".join(b.text for b in resp.content if b.type == "text"), "source": "claude"}
    except Exception as e:  # noqa: BLE001
        return {"text": _fallback(analysis, message), "source": "offline", "error": str(e)[:200]}
