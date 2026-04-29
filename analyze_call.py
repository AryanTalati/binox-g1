"""
analyze_call.py — Loop 2: Outcome Analysis
Reads a call transcript, uses Claude to produce a structured analysis
(objections raised, sentiment, score, what worked/failed), and appends
the result to outcomes.json.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic

BASE = Path(__file__).parent
DATA = BASE / "data"
TRANSCRIPTS = BASE / "transcripts"

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def load_json(path: Path) -> dict | list:
    with open(path) as f:
        return json.load(f)


def save_json(path: Path, data: dict | list) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


ANALYSIS_SYSTEM = """You are a sales coaching AI. You analyze cold call transcripts and produce structured JSON feedback.
Your output must be valid JSON only — no markdown, no preamble.

Return exactly this structure:
{
  "overall_score": <integer 1-10>,
  "outcome_label": "<converted|interested|neutral|rejected|hung_up>",
  "sentiment_arc": "<starts_positive|starts_neutral|starts_negative> → <ends_positive|ends_neutral|ends_negative>",
  "objections_raised": [
    {"objection": "<exact or paraphrased objection>", "handled": <true|false>, "handling_quality": "<good|weak|missing>"}
  ],
  "stage_performance": {
    "greeting": "<strong|adequate|weak>",
    "discovery": "<strong|adequate|weak>",
    "pitch": "<strong|adequate|weak>",
    "close": "<strong|adequate|weak|not_reached>"
  },
  "what_worked": ["<specific observation>"],
  "what_failed": ["<specific observation>"],
  "key_insight": "<one sentence: the single most important lesson from this call>",
  "suggested_script_changes": [
    {"stage": "<stage_name>", "change_type": "<add_handler|rewrite_line|add_discovery_question>", "rationale": "<why>", "suggested_text": "<new text>"}
  ]
}"""


def analyze_call(call_id: str) -> dict:
    transcript_path = TRANSCRIPTS / f"{call_id}.json"
    if not transcript_path.exists():
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")

    call_data = load_json(transcript_path)

    # Format transcript for Claude
    formatted = "\n".join(
        f"[Turn {t['turn']}] {t['speaker'].upper()}: {t['text']}"
        for t in call_data["transcript"]
    )

    prompt = f"""Analyze this sales call transcript.

CALL METADATA:
- Script version: {call_data['script_version']}
- Prospect persona: {call_data['persona']['name']}, {call_data['persona']['role']} at {call_data['persona']['company']}
- Declared outcome: {call_data['outcome']}
- Total agent turns: {call_data['turn_count']}

TRANSCRIPT:
{formatted}

Provide your structured JSON analysis."""

    print(f"\nAnalyzing call: {call_id}")

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1000,
        system=ANALYSIS_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = resp.content[0].text.strip()

    # Strip potential markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    analysis = json.loads(raw)
    analysis["call_id"] = call_id
    analysis["script_version"] = call_data["script_version"]
    analysis["persona_id"] = call_data["persona"]["id"]
    analysis["analyzed_at"] = datetime.now(timezone.utc).isoformat()

    # Append to outcomes log
    outcomes_path = DATA / "outcomes.json"
    outcomes = load_json(outcomes_path)
    outcomes.append(analysis)
    save_json(outcomes_path, outcomes)

    print(f"Score: {analysis['overall_score']}/10 | Outcome: {analysis['outcome_label']}")
    print(f"Key insight: {analysis['key_insight']}")
    print(f"Suggested changes: {len(analysis['suggested_script_changes'])}")
    print(f"Appended to outcomes.json ({len(outcomes)} total calls)")

    return analysis


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_call.py <call_id>")
        sys.exit(1)
    call_id = sys.argv[1]
    analyze_call(call_id)
