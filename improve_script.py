"""
improve_script.py — Loop 3: Script Improvement
Reads all outcomes in outcomes.json, aggregates patterns, and uses
Claude to produce an improved version of script.json. Documents every
change in changes.json with before/after and rationale.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic

BASE = Path(__file__).parent
DATA = BASE / "data"

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def load_json(path: Path) -> dict | list:
    with open(path) as f:
        return json.load(f)


def save_json(path: Path, data: dict | list) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


IMPROVEMENT_SYSTEM = """You are a sales script optimization AI. You receive:
1. The current sales script (JSON)
2. Aggregated analysis from recent calls

Your job is to produce an improved script JSON with the EXACT same structure as the input script.
Rules:
- Only output valid JSON — no markdown, no preamble
- Increment the "version" field by 1
- Update "updated_at" to the current ISO timestamp
- For each stage, you may:
  * Rewrite "agent_line" if it performed poorly
  * Add or update entries in "objection_handlers" (key = paraphrased objection, value = suggested response)
- Add a brief entry to "improvement_notes" explaining the changes made
- Do NOT change the structure of the JSON — same keys, same nesting
- Make targeted changes only — don't rewrite everything if only one stage is weak"""


def aggregate_outcomes(outcomes: list) -> str:
    if not outcomes:
        return "No outcomes yet."

    total = len(outcomes)
    avg_score = sum(o["overall_score"] for o in outcomes) / total
    outcome_counts = {}
    for o in outcomes:
        outcome_counts[o["outcome_label"]] = outcome_counts.get(o["outcome_label"], 0) + 1

    all_objections: dict[str, dict] = {}
    for o in outcomes:
        for obj in o.get("objections_raised", []):
            key = obj["objection"].lower()[:60]
            if key not in all_objections:
                all_objections[key] = {"count": 0, "handled": 0}
            all_objections[key]["count"] += 1
            if obj.get("handled"):
                all_objections[key]["handled"] += 1

    stage_scores: dict[str, dict] = {}
    for o in outcomes:
        for stage, rating in o.get("stage_performance", {}).items():
            if stage not in stage_scores:
                stage_scores[stage] = {"strong": 0, "adequate": 0, "weak": 0, "not_reached": 0}
            stage_scores[stage][rating] = stage_scores[stage].get(rating, 0) + 1

    all_suggestions = []
    for o in outcomes:
        all_suggestions.extend(o.get("suggested_script_changes", []))

    key_insights = [o.get("key_insight", "") for o in outcomes if o.get("key_insight")]

    lines = [
        f"AGGREGATED OUTCOMES ({total} calls):",
        f"Average score: {avg_score:.1f}/10",
        f"Outcome distribution: {json.dumps(outcome_counts)}",
        "",
        "TOP OBJECTIONS (frequency, handle rate):",
    ]
    top_objections = sorted(all_objections.items(), key=lambda x: -x[1]["count"])[:5]
    for obj_text, stats in top_objections:
        handle_rate = (stats["handled"] / stats["count"] * 100) if stats["count"] else 0
        lines.append(f"  - '{obj_text}': raised {stats['count']}x, handled {handle_rate:.0f}% of time")

    lines += ["", "STAGE PERFORMANCE:"]
    for stage, counts in stage_scores.items():
        weak_pct = (counts.get("weak", 0) / total * 100) if total else 0
        lines.append(f"  - {stage}: strong={counts.get('strong',0)}, adequate={counts.get('adequate',0)}, weak={counts.get('weak',0)} ({weak_pct:.0f}% weak)")

    lines += ["", "ALL SUGGESTED CHANGES FROM ANALYSES:"]
    for s in all_suggestions:
        lines.append(f"  - [{s['stage']}] {s['change_type']}: {s['rationale']}")
        if s.get("suggested_text"):
            lines.append(f"    Suggested: \"{s['suggested_text']}\"")

    lines += ["", "KEY INSIGHTS FROM CALLS:"]
    for insight in key_insights:
        lines.append(f"  - {insight}")

    return "\n".join(lines)


def improve_script(min_calls: int = 1) -> dict:
    outcomes_path = DATA / "outcomes.json"
    script_path = DATA / "script.json"
    changes_path = DATA / "changes.json"

    outcomes = load_json(outcomes_path)
    script = load_json(script_path)

    if len(outcomes) < min_calls:
        print(f"Only {len(outcomes)} outcome(s) — need {min_calls} minimum to improve. Skipping.")
        return script

    current_version = script["version"]
    aggregated = aggregate_outcomes(outcomes)

    print(f"\nImproving script from v{current_version} → v{current_version + 1}")
    print(f"Based on {len(outcomes)} call(s)")

    prompt = f"""Here is the current sales script:

{json.dumps(script, indent=2)}

Here is the aggregated performance data from recent calls:

{aggregated}

Produce an improved version of this script JSON. Current timestamp: {datetime.now(timezone.utc).isoformat()}"""

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        system=IMPROVEMENT_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = resp.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    new_script = json.loads(raw)

    # Log the change
    change_entry = {
        "from_version": current_version,
        "to_version": new_script["version"],
        "improved_at": datetime.now(timezone.utc).isoformat(),
        "based_on_n_calls": len(outcomes),
        "improvement_notes": new_script.get("improvement_notes", []),
        "script_before": script,
        "script_after": new_script,
    }

    changes = load_json(changes_path)
    changes.append(change_entry)
    save_json(changes_path, changes)
    save_json(script_path, new_script)

    # Clear outcomes so next iteration starts fresh
    save_json(outcomes_path, [])

    print(f"Script updated to v{new_script['version']}")
    print(f"Improvement notes: {new_script.get('improvement_notes', [])}")
    print(f"Change logged to changes.json ({len(changes)} total improvements)")

    return new_script


if __name__ == "__main__":
    min_calls = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    improve_script(min_calls)
