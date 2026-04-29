"""
run_cycle.py — Full Demo Runner
Runs one complete iteration cycle:
  1. Simulate a call (Loop 1)
  2. Analyze the transcript (Loop 2)
  3. Optionally improve the script (Loop 3)

Usage:
  python run_cycle.py                    # random persona, improve after 1 call
  python run_cycle.py --persona persona_budget
  python run_cycle.py --cycles 2         # run 2 full cycles back to back
  python run_cycle.py --no-improve       # skip Loop 3
"""

import argparse
import sys
from pathlib import Path

# Ensure scripts resolve relative to this file
sys.path.insert(0, str(Path(__file__).parent))

from run_call import run_call
from analyze_call import analyze_call
from improve_script import improve_script


def run_cycle(persona_id: str | None = None, should_improve: bool = True) -> None:
    print("\n" + "=" * 60)
    print("CYCLE START")
    print("=" * 60)

    # Loop 1 — Call
    print("\n[LOOP 1] Running call simulation...")
    call_result = run_call(persona_id)
    call_id = call_result["call_id"]

    # Loop 2 — Analysis
    print("\n[LOOP 2] Analyzing transcript...")
    analysis = analyze_call(call_id)

    # Loop 3 — Improvement
    if should_improve:
        print("\n[LOOP 3] Running script improvement...")
        improve_script(min_calls=1)
    else:
        print("\n[LOOP 3] Skipped (--no-improve flag set)")

    print("\n" + "=" * 60)
    print("CYCLE COMPLETE")
    print(f"  Call ID:   {call_id}")
    print(f"  Score:     {analysis['overall_score']}/10")
    print(f"  Outcome:   {analysis['outcome_label']}")
    print(f"  Insight:   {analysis['key_insight']}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Run G1 agent cycles")
    parser.add_argument("--persona", default=None, help="Persona ID to use (default: random)")
    parser.add_argument("--cycles", type=int, default=1, help="Number of cycles to run")
    parser.add_argument("--no-improve", action="store_true", help="Skip Loop 3 (script improvement)")
    args = parser.parse_args()

    for i in range(args.cycles):
        if args.cycles > 1:
            print(f"\n\n{'#'*60}")
            print(f"  ITERATION {i+1} of {args.cycles}")
            print(f"{'#'*60}")
        run_cycle(
            persona_id=args.persona,
            should_improve=not args.no_improve,
        )


if __name__ == "__main__":
    main()
