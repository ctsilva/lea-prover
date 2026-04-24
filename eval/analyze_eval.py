"""Analyze completed evaluation runs with detailed statistics.

Usage:
    python -m eval.analyze_eval RESULTS_FILE.json          # Analyze specific eval
    python -m eval.analyze_eval --latest                   # Analyze latest eval
    python -m eval.analyze_eval --export stats.json        # Export to JSON
    python -m eval.analyze_eval --compare FILE1 FILE2      # Compare two evals
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel


def find_latest_results() -> Path | None:
    """Find the most recent results JSON file."""
    results_dir = Path(__file__).parent / "results"
    if not results_dir.exists():
        return None

    json_files = [f for f in results_dir.glob("*.json")]
    if not json_files:
        return None

    return max(json_files, key=lambda p: p.stat().st_mtime)


def load_results(path: Path) -> dict:
    """Load results JSON."""
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error loading {path}: {e}", file=sys.stderr)
        sys.exit(1)


def analyze_eval_results(results: dict) -> dict:
    """Analyze evaluation results and extract statistics.

    Returns:
        Dict with comprehensive analysis
    """
    completed = results.get("completed", {})

    if not completed:
        return {"error": "No completed problems"}

    # Basic stats
    total = len(completed)
    passed = sum(1 for r in completed.values() if r.get("success"))
    failed = total - passed

    # Time statistics
    times = [r.get("time_s", 0) for r in completed.values()]
    avg_time = sum(times) / len(times) if times else 0
    min_time = min(times) if times else 0
    max_time = max(times) if times else 0

    # Turn statistics
    turns_list = [r.get("turns", 0) for r in completed.values()]
    avg_turns = sum(turns_list) / len(turns_list) if turns_list else 0
    min_turns = min(turns_list) if turns_list else 0
    max_turns = max(turns_list) if turns_list else 0

    # Token statistics
    total_input_tokens = 0
    total_output_tokens = 0
    for r in completed.values():
        usage = r.get("usage", {})
        total_input_tokens += usage.get("input_tokens", 0)
        total_output_tokens += usage.get("output_tokens", 0)

    total_tokens = total_input_tokens + total_output_tokens
    avg_tokens = total_tokens / total if total else 0

    # Success vs failure comparisons
    passed_times = [r.get("time_s", 0) for r in completed.values() if r.get("success")]
    failed_times = [r.get("time_s", 0) for r in completed.values() if not r.get("success")]

    passed_turns = [r.get("turns", 0) for r in completed.values() if r.get("success")]
    failed_turns = [r.get("turns", 0) for r in completed.values() if not r.get("success")]

    # Find hardest problems (most turns, failed)
    hardest = sorted(
        [(k, v.get("turns", 0), v.get("time_s", 0)) for k, v in completed.items() if not v.get("success")],
        key=lambda x: x[1],
        reverse=True
    )[:10]

    # Find quickest successes
    quickest = sorted(
        [(k, v.get("time_s", 0), v.get("turns", 0)) for k, v in completed.items() if v.get("success")],
        key=lambda x: x[1]
    )[:10]

    return {
        "meta": {
            "split": results.get("split", "unknown"),
            "model": results.get("model", "unknown"),
            "max_turns": results.get("max_turns", 0),
        },
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": (passed / total * 100) if total else 0,
        },
        "time_stats": {
            "avg": avg_time,
            "min": min_time,
            "max": max_time,
            "passed_avg": sum(passed_times) / len(passed_times) if passed_times else 0,
            "failed_avg": sum(failed_times) / len(failed_times) if failed_times else 0,
        },
        "turn_stats": {
            "avg": avg_turns,
            "min": min_turns,
            "max": max_turns,
            "passed_avg": sum(passed_turns) / len(passed_turns) if passed_turns else 0,
            "failed_avg": sum(failed_turns) / len(failed_turns) if failed_turns else 0,
        },
        "token_stats": {
            "total": total_tokens,
            "avg_per_problem": avg_tokens,
            "input": total_input_tokens,
            "output": total_output_tokens,
        },
        "hardest_problems": hardest,
        "quickest_successes": quickest,
    }


def print_analysis(analysis: dict, console: Console, results_path: Path):
    """Print formatted analysis."""

    meta = analysis["meta"]
    summary = analysis["summary"]
    time_stats = analysis["time_stats"]
    turn_stats = analysis["turn_stats"]
    token_stats = analysis["token_stats"]

    # Header
    console.print(Panel(
        f"[bold]miniF2F Evaluation Analysis[/bold]\n"
        f"File: {results_path.name}\n"
        f"Split: {meta['split']} | Model: {meta['model']} | Max turns: {meta['max_turns']}",
        style="cyan"
    ))
    console.print()

    # Summary Table
    summary_table = Table(title="Summary", show_header=True, header_style="bold magenta")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", justify="right")

    summary_table.add_row("Total Problems", str(summary["total"]))
    summary_table.add_row("Passed", f"[green]{summary['passed']}[/green]")
    summary_table.add_row("Failed", f"[red]{summary['failed']}[/red]")
    summary_table.add_row("Pass Rate", f"[bold]{summary['pass_rate']:.1f}%[/bold]")

    console.print(summary_table)
    console.print()

    # Time Statistics
    time_table = Table(title="Time Statistics (seconds)", show_header=True, header_style="bold green")
    time_table.add_column("Metric", style="cyan")
    time_table.add_column("All", justify="right")
    time_table.add_column("Passed", justify="right")
    time_table.add_column("Failed", justify="right")

    time_table.add_row("Average", f"{time_stats['avg']:.1f}", f"{time_stats['passed_avg']:.1f}", f"{time_stats['failed_avg']:.1f}")
    time_table.add_row("Min", f"{time_stats['min']:.1f}", "", "")
    time_table.add_row("Max", f"{time_stats['max']:.1f}", "", "")

    console.print(time_table)
    console.print()

    # Turn Statistics
    turn_table = Table(title="Turn Statistics", show_header=True, header_style="bold yellow")
    turn_table.add_column("Metric", style="cyan")
    turn_table.add_column("All", justify="right")
    turn_table.add_column("Passed", justify="right")
    turn_table.add_column("Failed", justify="right")

    turn_table.add_row("Average", f"{turn_stats['avg']:.1f}", f"{turn_stats['passed_avg']:.1f}", f"{turn_stats['failed_avg']:.1f}")
    turn_table.add_row("Min", str(turn_stats['min']), "", "")
    turn_table.add_row("Max", str(turn_stats['max']), "", "")

    console.print(turn_table)
    console.print()

    # Token Statistics
    token_table = Table(title="Token Usage", show_header=True, header_style="bold blue")
    token_table.add_column("Metric", style="cyan")
    token_table.add_column("Value", justify="right")

    token_table.add_row("Total", f"{token_stats['total']:,}")
    token_table.add_row("Input", f"{token_stats['input']:,}")
    token_table.add_row("Output", f"{token_stats['output']:,}")
    token_table.add_row("Avg per problem", f"{token_stats['avg_per_problem']:,.0f}")

    console.print(token_table)
    console.print()

    # Hardest Problems
    if analysis["hardest_problems"]:
        hardest_table = Table(title="Hardest Problems (Failed, Most Turns)", show_header=True, header_style="bold red")
        hardest_table.add_column("Problem", style="dim", width=30, overflow="fold")
        hardest_table.add_column("Turns", justify="right")
        hardest_table.add_column("Time (s)", justify="right")

        for name, turns, time_s in analysis["hardest_problems"][:5]:
            hardest_table.add_row(name, str(turns), f"{time_s:.0f}")

        console.print(hardest_table)
        console.print()

    # Quickest Successes
    if analysis["quickest_successes"]:
        quickest_table = Table(title="Quickest Successes", show_header=True, header_style="bold green")
        quickest_table.add_column("Problem", style="dim", width=30, overflow="fold")
        quickest_table.add_column("Turns", justify="right")
        quickest_table.add_column("Time (s)", justify="right")

        for name, time_s, turns in analysis["quickest_successes"][:5]:
            quickest_table.add_row(name, str(turns), f"{time_s:.0f}")

        console.print(quickest_table)


def compare_evals(results1: dict, results2: dict, path1: Path, path2: Path) -> dict:
    """Compare two evaluation runs."""
    analysis1 = analyze_eval_results(results1)
    analysis2 = analyze_eval_results(results2)

    return {
        "eval1": {
            "file": path1.name,
            "meta": analysis1["meta"],
            "summary": analysis1["summary"],
            "time_avg": analysis1["time_stats"]["avg"],
            "turns_avg": analysis1["turn_stats"]["avg"],
            "tokens_total": analysis1["token_stats"]["total"],
        },
        "eval2": {
            "file": path2.name,
            "meta": analysis2["meta"],
            "summary": analysis2["summary"],
            "time_avg": analysis2["time_stats"]["avg"],
            "turns_avg": analysis2["turn_stats"]["avg"],
            "tokens_total": analysis2["token_stats"]["total"],
        }
    }


def print_comparison(comparison: dict, console: Console):
    """Print comparison of two evals."""
    e1 = comparison["eval1"]
    e2 = comparison["eval2"]

    console.print(Panel(
        f"[bold]Comparing Evaluations[/bold]\n"
        f"{e1['file']} vs {e2['file']}",
        style="cyan"
    ))
    console.print()

    # Comparison table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric")
    table.add_column(e1["file"][:20], justify="right")
    table.add_column(e2["file"][:20], justify="right")
    table.add_column("Difference", justify="right")

    # Models
    table.add_row("Model", e1["meta"]["model"][:20], e2["meta"]["model"][:20], "")

    # Pass rates
    table.add_row(
        "Pass Rate",
        f"{e1['summary']['pass_rate']:.1f}%",
        f"{e2['summary']['pass_rate']:.1f}%",
        f"{e2['summary']['pass_rate'] - e1['summary']['pass_rate']:+.1f}%"
    )

    # Problems passed
    table.add_row(
        "Passed",
        str(e1["summary"]["passed"]),
        str(e2["summary"]["passed"]),
        f"{e2['summary']['passed'] - e1['summary']['passed']:+d}"
    )

    # Average time
    table.add_row(
        "Avg Time (s)",
        f"{e1['time_avg']:.1f}",
        f"{e2['time_avg']:.1f}",
        f"{e2['time_avg'] - e1['time_avg']:+.1f}"
    )

    # Average turns
    table.add_row(
        "Avg Turns",
        f"{e1['turns_avg']:.1f}",
        f"{e2['turns_avg']:.1f}",
        f"{e2['turns_avg'] - e1['turns_avg']:+.1f}"
    )

    # Total tokens
    table.add_row(
        "Total Tokens",
        f"{e1['tokens_total']:,}",
        f"{e2['tokens_total']:,}",
        f"{e2['tokens_total'] - e1['tokens_total']:+,}"
    )

    console.print(table)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Analyze miniF2F evaluation results")
    parser.add_argument("results_file", nargs="?", help="Path to results JSON file")
    parser.add_argument("--latest", action="store_true", help="Analyze the most recent eval")
    parser.add_argument("--export", metavar="FILE", help="Export analysis to JSON file")
    parser.add_argument("--compare", nargs=2, metavar=("FILE1", "FILE2"), help="Compare two eval runs")

    args = parser.parse_args()

    console = Console()

    if args.compare:
        # Compare mode
        path1 = Path(args.compare[0])
        path2 = Path(args.compare[1])

        results1 = load_results(path1)
        results2 = load_results(path2)

        comparison = compare_evals(results1, results2, path1, path2)
        print_comparison(comparison, console)

    else:
        # Single analysis mode
        if args.results_file:
            results_path = Path(args.results_file)
        elif args.latest:
            results_path = find_latest_results()
            if not results_path:
                print("Error: No results files found in eval/results/", file=sys.stderr)
                sys.exit(1)
        else:
            parser.print_help()
            sys.exit(1)

        results = load_results(results_path)
        analysis = analyze_eval_results(results)

        if "error" in analysis:
            console.print(f"[red]Error: {analysis['error']}[/red]")
            sys.exit(1)

        # Export if requested
        if args.export:
            export_path = Path(args.export)
            export_path.write_text(json.dumps(analysis, indent=2))
            console.print(f"[green]Analysis exported to: {export_path}[/green]\n")

        # Print to console
        print_analysis(analysis, console, results_path)


if __name__ == "__main__":
    main()
