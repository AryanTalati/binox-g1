"""
run_call.py — Loop 1: Simulated Sales Call
Conducts a text-based mock conversation (STT/TTS simulation) between
the AI agent (using the current script.json) and a prospect persona.
Saves a full transcript to transcripts/.
"""

import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic

BASE = Path(__file__).parent
DATA = BASE / "data"
TRANSCRIPTS = BASE / "transcripts"
TRANSCRIPTS.mkdir(exist_ok=True)

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def load_json(path: Path) -> dict | list:
    with open(path) as f:
        return json.load(f)


def save_json(path: Path, data: dict | list) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def mock_tts(speaker: str, text: str) -> None:
    """Simulate TTS output — prints with a speaker label."""
    tag = "🤖 AGENT" if speaker == "agent" else "👤 PROSPECT"
    print(f"\n{tag}: {text}")


def mock_stt(text: str) -> str:
    """Simulate STT — in a real system this would transcribe audio."""
    return text


def build_agent_system_prompt(script: dict) -> str:
    stages_text = "\n".join(
        f"- {name}: {stage['agent_line']}\n  (goal: {stage['goal']})"
        for name, stage in script["stages"].items()
    )
    objection_handlers = {}
    for stage_name, stage in script["stages"].items():
        objection_handlers.update(stage.get("objection_handlers", {}))

    handlers_text = (
        "\n".join(f"- If prospect says '{k}': {v}" for k, v in objection_handlers.items())
        if objection_handlers
        else "No specific handlers yet — improvise based on the value proposition."
    )

    return f"""You are Alex, a friendly and professional sales representative for CloudSuite CRM.
You are on a cold call. Follow this script structure, progressing naturally through stages:

SCRIPT STAGES:
{stages_text}

OBJECTION HANDLERS:
{handlers_text}

RULES:
- Stay in character as Alex at all times.
- Keep each response to 2-3 sentences maximum.
- Progress through stages naturally — don't skip stages.
- Handle objections before progressing.
- If the prospect is clearly not interested after 2 attempts, wrap up politely.
- Never break character or discuss the script itself.
- Output ONLY your spoken dialogue — no stage labels, no meta-commentary.
"""


def build_prospect_system_prompt(persona: dict) -> str:
    return f"""You are {persona['name']}, {persona['role']} at {persona['company']}.
Personality: {persona['personality']}
Your likely objections: {', '.join(persona['likely_objections'])}

You are receiving an unexpected cold call from a software salesperson.
RULES:
- Stay in character throughout.
- Start mildly sceptical or neutral — this is a cold call.
- Raise at least 2 of your typical objections naturally during the conversation.
- You may eventually show interest if the agent addresses your concerns well.
- Keep responses to 1-2 sentences.
- After 6-8 exchanges, reach a natural conclusion (either agree to next step or decline).
- Output ONLY your spoken dialogue.
"""


def run_call(persona_id: str | None = None) -> dict:
    script = load_json(DATA / "script.json")
    personas = load_json(DATA / "personas.json")

    persona = (
        next((p for p in personas if p["id"] == persona_id), None)
        if persona_id
        else random.choice(personas)
    )

    print(f"\n{'='*60}")
    print(f"CALL SIMULATION — Script v{script['version']}")
    print(f"Prospect: {persona['name']} ({persona['role']}, {persona['company']})")
    print(f"{'='*60}")

    agent_messages = [{"role": "user", "content": "Begin the call now."}]
    
    prospect_messages = []
    transcript = []

    agent_system = build_agent_system_prompt(script)
    prospect_system = build_prospect_system_prompt(persona)

    max_turns = 10
    outcome = "incomplete"

    for turn in range(max_turns):
        # --- Agent turn ---
        agent_resp = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=200,
            system=agent_system,
            messages=agent_messages,
        )
        agent_text = agent_resp.content[0].text.strip()
        mock_tts("agent", agent_text)

        agent_messages.append({"role": "assistant", "content": agent_text})
        prospect_messages.append({"role": "user", "content": f"[Sales agent says:] {agent_text}"})
        transcript.append({"turn": turn + 1, "speaker": "agent", "text": agent_text})

        # --- Check for natural call end from agent ---
        end_phrases = ["thank you for your time", "have a great day", "i'll let you go", "take care"]
        if any(p in agent_text.lower() for p in end_phrases) and turn > 3:
            outcome = "completed"
            break

        # --- Prospect turn ---
        prospect_resp = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=150,
            system=prospect_system,
            messages=prospect_messages,
        )
        prospect_text = prospect_resp.content[0].text.strip()
        mock_tts("prospect", prospect_text)

        prospect_messages.append({"role": "assistant", "content": prospect_text})
        agent_messages.append({"role": "user", "content": prospect_text})
        transcript.append({"turn": turn + 1, "speaker": "prospect", "text": prospect_text})

        # --- Check for early hang-up ---
        hangup_phrases = ["not interested", "please remove", "do not call", "goodbye", "i have to go"]
        if any(p in prospect_text.lower() for p in hangup_phrases) and turn > 1:
            outcome = "hung_up"
            break

    call_id = f"call_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{persona['id']}"
    result = {
        "call_id": call_id,
        "script_version": script["version"],
        "persona": persona,
        "transcript": transcript,
        "outcome": outcome,
        "turn_count": len([t for t in transcript if t["speaker"] == "agent"]),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    transcript_path = TRANSCRIPTS / f"{call_id}.json"
    save_json(transcript_path, result)

    print(f"\n{'='*60}")
    print(f"Call ended. Outcome: {outcome.upper()} | Turns: {result['turn_count']}")
    print(f"Transcript saved → {transcript_path}")

    return result


if __name__ == "__main__":
    persona_id = sys.argv[1] if len(sys.argv) > 1 else None
    result = run_call(persona_id)
    # Print the call_id so n8n can pick it up
    print(f"\nCALL_ID:{result['call_id']}")
