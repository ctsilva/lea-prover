#!/usr/bin/env python3
"""
Compare multiple sessions solving the same problem.

Usage:
    python eval/compare_sessions.py <problem_name> <eval_results_dir>

Example:
    python eval/compare_sessions.py aimeII_2001_p3 eval_results/test_run/
"""

import json
import sys
from pathlib import Path

def find_sessions_for_problem(problem_name: str, base_dir: Path):
    """Find all sessions for a specific problem."""
    problem_dir = base_dir / problem_name
    if not problem_dir.exists():
        return []

    sessions = []
    for session_dir in sorted(problem_dir.iterdir()):
        if not session_dir.is_dir():
            continue

        metadata_file = session_dir / "metadata.json"
        final_result_file = session_dir / "final_result.json"

        if not metadata_file.exists() or not final_result_file.exists():
            continue

        with open(metadata_file) as f:
            metadata = json.load(f)

        with open(final_result_file) as f:
            final_result = json.load(f)

        sessions.append({
            "session_id": final_result.get("session_id", session_dir.name),
            "session_dir": session_dir,
            "metadata": metadata,
            "final_result": final_result
        })

    return sessions

def compare_sessions(sessions):
    """Compare multiple sessions."""
    print("\n" + "="*80)
    print(f"COMPARING {len(sessions)} SESSIONS")
    print("="*80 + "\n")

    for i, session in enumerate(sessions, 1):
        final = session["final_result"]
        meta = session["metadata"]

        status = "✓ PASS" if final.get("success") else "✗ FAIL"
        turns = final.get("turns", 0)
        usage = final.get("usage", {})
        total_tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

        print(f"Session {i}: {session['session_id']}")
        print(f"  Status:      {status}")
        print(f"  Turns:       {turns}")
        print(f"  Tokens:      {total_tokens:,}")
        print(f"  Model:       {meta.get('model', 'unknown')}")
        print(f"  Started:     {meta.get('started_at', 'unknown')[:19]}")

        if final.get("error"):
            print(f"  Error:       {final['error'][:100]}...")

        print()

    # Summary comparison
    passed = [s for s in sessions if s["final_result"].get("success")]
    failed = [s for s in sessions if not s["final_result"].get("success")]

    print("="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Passed:  {len(passed)}/{len(sessions)} ({len(passed)/len(sessions)*100:.0f}%)")
    print(f"Failed:  {len(failed)}/{len(sessions)} ({len(failed)/len(sessions)*100:.0f}%)")

    if passed:
        avg_turns = sum(s["final_result"].get("turns", 0) for s in passed) / len(passed)
        avg_tokens = sum(
            s["final_result"].get("usage", {}).get("input_tokens", 0) +
            s["final_result"].get("usage", {}).get("output_tokens", 0)
            for s in passed
        ) / len(passed)
        print(f"\nWhen successful:")
        print(f"  Avg turns:   {avg_turns:.1f}")
        print(f"  Avg tokens:  {avg_tokens:,.0f}")

    if len(passed) > 1:
        best = min(passed, key=lambda s: s["final_result"].get("turns", 999))
        print(f"\nBest solution: {best['session_id']}")
        print(f"  Turns:  {best['final_result'].get('turns')}")

    print("\n" + "="*80 + "\n")

def main():
    if len(sys.argv) < 3:
        print("Usage: python eval/compare_sessions.py <problem_name> <eval_results_dir>")
        print("\nExample:")
        print("  python eval/compare_sessions.py aimeII_2001_p3 eval_results/test_run/")
        sys.exit(1)

    problem_name = sys.argv[1]
    base_dir = Path(sys.argv[2])

    if not base_dir.exists():
        print(f"Error: Directory not found: {base_dir}")
        sys.exit(1)

    sessions = find_sessions_for_problem(problem_name, base_dir)

    if not sessions:
        print(f"No sessions found for problem: {problem_name}")
        print(f"\nAvailable problems:")
        for prob_dir in sorted(base_dir.iterdir()):
            if prob_dir.is_dir() and not prob_dir.name.startswith("."):
                print(f"  - {prob_dir.name}")
        sys.exit(1)

    compare_sessions(sessions)

if __name__ == "__main__":
    main()
