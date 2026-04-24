#!/usr/bin/env python3
"""
Analyze evaluation results and generate insights.

Usage:
    python eval/analyze_results.py <eval_results_dir>
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
import statistics

def load_all_results(base_dir: Path):
    """Load all session results."""
    results = []

    for final_result_file in base_dir.rglob("final_result.json"):
        session_dir = final_result_file.parent

        # Load final result
        with open(final_result_file) as f:
            final_result = json.load(f)

        # Load metadata
        metadata_file = session_dir / "metadata.json"
        metadata = {}
        if metadata_file.exists():
            with open(metadata_file) as f:
                metadata = json.load(f)

        # Load timeline for tool analysis
        timeline_file = session_dir / "tool_timeline.jsonl"
        timeline = []
        if timeline_file.exists():
            with open(timeline_file) as f:
                timeline = [json.loads(line) for line in f]

        problem_name = session_dir.parent.name

        results.append({
            "problem": problem_name,
            "session_id": final_result.get("session_id", session_dir.name),
            "success": final_result.get("success", False),
            "turns": final_result.get("turns", 0),
            "usage": final_result.get("usage", {}),
            "error": final_result.get("error"),
            "timeline": timeline,
            "metadata": metadata
        })

    return results

def analyze_results(results):
    """Generate insights from results."""
    total = len(results)
    passed = sum(1 for r in results if r["success"])
    failed = total - passed

    # Success rate
    success_rate = passed / total if total > 0 else 0

    # Turn statistics
    turns_all = [r["turns"] for r in results]
    turns_passed = [r["turns"] for r in results if r["success"]]
    turns_failed = [r["turns"] for r in results if not r["success"]]

    # Token statistics
    total_input_tokens = sum(r["usage"].get("input_tokens", 0) for r in results)
    total_output_tokens = sum(r["usage"].get("output_tokens", 0) for r in results)
    total_tokens = total_input_tokens + total_output_tokens

    tokens_passed = sum(
        r["usage"].get("input_tokens", 0) + r["usage"].get("output_tokens", 0)
        for r in results if r["success"]
    )
    tokens_failed = total_tokens - tokens_passed

    # Tool usage analysis
    tool_counts = defaultdict(int)
    tool_durations = defaultdict(list)

    for result in results:
        for entry in result["timeline"]:
            tool = entry.get("tool", "unknown")
            tool_counts[tool] += 1
            tool_durations[tool].append(entry.get("duration_ms", 0))

    # Success by turn count
    success_by_turns = {}
    for r in results:
        turns = r["turns"]
        if turns not in success_by_turns:
            success_by_turns[turns] = {"passed": 0, "failed": 0}
        if r["success"]:
            success_by_turns[turns]["passed"] += 1
        else:
            success_by_turns[turns]["failed"] += 1

    insights = {
        "overview": {
            "total_problems": total,
            "passed": passed,
            "failed": failed,
            "success_rate": success_rate
        },
        "turns": {
            "avg_all": statistics.mean(turns_all) if turns_all else 0,
            "avg_passed": statistics.mean(turns_passed) if turns_passed else 0,
            "avg_failed": statistics.mean(turns_failed) if turns_failed else 0,
            "min": min(turns_all) if turns_all else 0,
            "max": max(turns_all) if turns_all else 0
        },
        "tokens": {
            "total": total_tokens,
            "total_input": total_input_tokens,
            "total_output": total_output_tokens,
            "avg_per_problem": total_tokens / total if total > 0 else 0,
            "passed_total": tokens_passed,
            "failed_total": tokens_failed,
            "avg_passed": tokens_passed / passed if passed > 0 else 0,
            "avg_failed": tokens_failed / failed if failed > 0 else 0
        },
        "tools": {
            "most_used": sorted(tool_counts.items(), key=lambda x: -x[1])[:10],
            "slowest": sorted(
                [(tool, statistics.mean(durs)) for tool, durs in tool_durations.items()],
                key=lambda x: -x[1]
            )[:10]
        },
        "success_by_turns": success_by_turns,
        "problems": results
    }

    return insights

def print_insights(insights):
    """Print formatted insights."""
    print("\n" + "="*70)
    print("EVALUATION RESULTS ANALYSIS")
    print("="*70)

    # Overview
    ov = insights["overview"]
    print(f"\n📊 OVERVIEW")
    print(f"   Total Problems:  {ov['total_problems']}")
    print(f"   Passed:          {ov['passed']} ({ov['success_rate']*100:.1f}%)")
    print(f"   Failed:          {ov['failed']} ({(1-ov['success_rate'])*100:.1f}%)")

    # Turns
    t = insights["turns"]
    print(f"\n🔄 TURNS")
    print(f"   Average (all):   {t['avg_all']:.1f} turns")
    print(f"   Average (pass):  {t['avg_passed']:.1f} turns")
    print(f"   Average (fail):  {t['avg_failed']:.1f} turns")
    print(f"   Range:           {t['min']} - {t['max']} turns")

    # Tokens
    tok = insights["tokens"]
    print(f"\n💰 TOKENS")
    print(f"   Total:           {tok['total']:,} tokens")
    print(f"   Input:           {tok['total_input']:,} tokens")
    print(f"   Output:          {tok['total_output']:,} tokens")
    print(f"   Avg per problem: {tok['avg_per_problem']:,.0f} tokens")
    print(f"   Avg when pass:   {tok['avg_passed']:,.0f} tokens")
    print(f"   Avg when fail:   {tok['avg_failed']:,.0f} tokens")

    # Tools
    print(f"\n🔧 TOP 10 MOST USED TOOLS")
    for tool, count in insights["tools"]["most_used"]:
        print(f"   {tool:20s} {count:4d} calls")

    print(f"\n⏱️  TOP 10 SLOWEST TOOLS (avg duration)")
    for tool, avg_dur in insights["tools"]["slowest"]:
        if avg_dur >= 1000:
            dur_str = f"{avg_dur/1000:.1f}s"
        else:
            dur_str = f"{avg_dur:.0f}ms"
        print(f"   {tool:20s} {dur_str}")

    # Success patterns
    print(f"\n🎯 SUCCESS PATTERNS BY TURN COUNT")
    for turns in sorted(insights["success_by_turns"].keys()):
        data = insights["success_by_turns"][turns]
        total = data["passed"] + data["failed"]
        rate = data["passed"] / total if total > 0 else 0
        print(f"   {turns:2d} turns: {data['passed']}/{total} passed ({rate*100:.0f}%)")

    # Problem breakdown
    print(f"\n📝 PROBLEM BREAKDOWN")
    for prob in sorted(insights["problems"], key=lambda x: x["problem"]):
        status = "✓ PASS" if prob["success"] else "✗ FAIL"
        tokens = prob["usage"].get("input_tokens", 0) + prob["usage"].get("output_tokens", 0)
        print(f"   {status} {prob['problem']:25s} {prob['turns']:2d} turns, {tokens:,} tokens")

    # Key insights
    print(f"\n💡 KEY INSIGHTS")

    if tok['avg_failed'] > tok['avg_passed']:
        ratio = tok['avg_failed'] / tok['avg_passed'] if tok['avg_passed'] > 0 else 0
        print(f"   • Failed problems use {ratio:.1f}x more tokens on average")

    if t['avg_failed'] > t['avg_passed']:
        print(f"   • Failed problems take {t['avg_failed'] - t['avg_passed']:.1f} more turns on average")

    # Check if there's a turn count sweet spot
    best_rate = 0
    best_turns = None
    for turns, data in insights["success_by_turns"].items():
        total = data["passed"] + data["failed"]
        if total >= 2:  # At least 2 samples
            rate = data["passed"] / total
            if rate > best_rate:
                best_rate = rate
                best_turns = turns

    if best_turns:
        print(f"   • Highest success rate at {best_turns} turns ({best_rate*100:.0f}%)")

    # Check for early vs late solving
    early_solves = [p for p in insights["problems"] if p["success"] and p["turns"] <= 10]
    late_solves = [p for p in insights["problems"] if p["success"] and p["turns"] > 10]

    if early_solves:
        avg_early_tokens = statistics.mean([
            p["usage"].get("input_tokens", 0) + p["usage"].get("output_tokens", 0)
            for p in early_solves
        ])
        print(f"   • {len(early_solves)} problems solved in ≤10 turns (avg {avg_early_tokens:,.0f} tokens)")

    if late_solves:
        avg_late_tokens = statistics.mean([
            p["usage"].get("input_tokens", 0) + p["usage"].get("output_tokens", 0)
            for p in late_solves
        ])
        print(f"   • {len(late_solves)} problems solved in >10 turns (avg {avg_late_tokens:,.0f} tokens)")

    print("\n" + "="*70 + "\n")

def save_insights(insights, output_file):
    """Save insights to JSON."""
    with open(output_file, 'w') as f:
        json.dump(insights, f, indent=2)
    print(f"✓ Detailed insights saved to: {output_file}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python eval/analyze_results.py <eval_results_dir>")
        print("\nExample:")
        print("  python eval/analyze_results.py eval_results/test_run/")
        sys.exit(1)

    base_dir = Path(sys.argv[1])
    if not base_dir.exists():
        print(f"Error: Directory not found: {base_dir}")
        sys.exit(1)

    print(f"Loading results from {base_dir}...")
    results = load_all_results(base_dir)

    if not results:
        print("No results found!")
        sys.exit(1)

    print(f"Analyzing {len(results)} sessions...")
    insights = analyze_results(results)

    print_insights(insights)

    # Save to JSON
    output_file = base_dir / "analysis.json"
    save_insights(insights, output_file)

if __name__ == "__main__":
    main()
