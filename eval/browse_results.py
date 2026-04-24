"""Browse all evaluation results across multiple runs.

Usage:
    python -m eval.browse_results                    # Browse eval_results/
    python -m eval.browse_results --dir custom_dir   # Browse custom directory
    python -m eval.browse_results --problem aimeII   # Filter by problem name
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel


def find_all_runs(base_dir: Path) -> dict:
    """Find all eval runs in a directory structure.

    Expected structure:
        eval_results/
            run_name/
                problem_name/
                    session_id/
                        metadata.json
                        final_result.json
                        ...

    Returns:
        {
            "run_name": {
                "problems": {
                    "problem_name": {
                        "session_id": "...",
                        "success": bool,
                        "turns": int,
                        "tokens": int,
                        ...
                    }
                }
            }
        }
    """
    runs = defaultdict(lambda: {"problems": {}})

    if not base_dir.exists():
        return {}

    # Look for structure: base_dir/run_name/problem_name/session_id/
    for run_dir in base_dir.iterdir():
        if not run_dir.is_dir():
            continue

        run_name = run_dir.name

        # Each subdirectory is a problem
        for problem_dir in run_dir.iterdir():
            if not problem_dir.is_dir():
                continue

            problem_name = problem_dir.name

            # Find session directories (timestamp format)
            session_dirs = [d for d in problem_dir.iterdir() if d.is_dir() and d.name[0].isdigit()]

            if not session_dirs:
                continue

            # Use the latest session for this problem
            latest_session = max(session_dirs, key=lambda d: d.stat().st_mtime)

            # Load metadata and final_result
            metadata_file = latest_session / "metadata.json"
            final_result_file = latest_session / "final_result.json"

            problem_info = {
                "session_id": latest_session.name,
                "session_path": latest_session,
            }

            if metadata_file.exists():
                try:
                    metadata = json.loads(metadata_file.read_text())
                    problem_info["model"] = metadata.get("config", {}).get("provider", "unknown")
                    problem_info["max_turns"] = metadata.get("config", {}).get("max_turns", 0)
                except:
                    pass

            if final_result_file.exists():
                try:
                    final = json.loads(final_result_file.read_text())
                    problem_info["success"] = final.get("success", False)
                    problem_info["turns"] = final.get("turns", 0)
                    problem_info["error"] = final.get("error")

                    usage = final.get("usage", {})
                    problem_info["tokens"] = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                except:
                    pass

            runs[run_name]["problems"][problem_name] = problem_info

    return dict(runs)


def print_runs_summary(runs: dict, console: Console, problem_filter: str = None):
    """Print a summary of all runs."""

    if not runs:
        console.print("[yellow]No evaluation runs found[/yellow]")
        return

    # Summary table
    summary_table = Table(title="Evaluation Runs Summary", show_header=True, header_style="bold cyan")
    summary_table.add_column("Run Name", style="cyan")
    summary_table.add_column("Problems", justify="right")
    summary_table.add_column("Passed", justify="right")
    summary_table.add_column("Failed", justify="right")
    summary_table.add_column("Pass Rate", justify="right")

    for run_name, run_data in sorted(runs.items()):
        problems = run_data["problems"]

        if problem_filter:
            problems = {k: v for k, v in problems.items() if problem_filter.lower() in k.lower()}
            if not problems:
                continue

        total = len(problems)
        passed = sum(1 for p in problems.values() if p.get("success"))
        failed = total - passed
        pass_rate = (passed / total * 100) if total else 0

        summary_table.add_row(
            run_name,
            str(total),
            f"[green]{passed}[/green]",
            f"[red]{failed}[/red]",
            f"{pass_rate:.1f}%"
        )

    console.print(summary_table)
    console.print()

    # Detailed per-run tables
    for run_name, run_data in sorted(runs.items()):
        problems = run_data["problems"]

        if problem_filter:
            problems = {k: v for k, v in problems.items() if problem_filter.lower() in k.lower()}
            if not problems:
                continue

        detail_table = Table(
            title=f"Run: {run_name}",
            show_header=True,
            header_style="bold magenta"
        )
        detail_table.add_column("Problem", style="dim", width=30, overflow="fold")
        detail_table.add_column("Result", width=6)
        detail_table.add_column("Turns", justify="right", width=6)
        detail_table.add_column("Tokens", justify="right", width=10)
        detail_table.add_column("Session", style="dim", width=16)

        for problem_name, info in sorted(problems.items()):
            success = info.get("success", False)
            result = "[green]PASS[/green]" if success else "[red]FAIL[/red]"
            turns = info.get("turns", 0)
            tokens = info.get("tokens", 0)
            session_id = info.get("session_id", "")[:16]

            detail_table.add_row(
                problem_name,
                result,
                str(turns),
                f"{tokens:,}",
                session_id
            )

        console.print(detail_table)
        console.print()


def print_problem_details(runs: dict, problem_name: str, console: Console):
    """Print detailed history for a specific problem across all runs."""

    history = []

    for run_name, run_data in runs.items():
        if problem_name in run_data["problems"]:
            info = run_data["problems"][problem_name]
            history.append({
                "run": run_name,
                **info
            })

    if not history:
        console.print(f"[yellow]No results found for problem: {problem_name}[/yellow]")
        return

    console.print(Panel(
        f"[bold]Problem History: {problem_name}[/bold]\n"
        f"Found in {len(history)} runs",
        style="cyan"
    ))
    console.print()

    table = Table(show_header=True, header_style="bold green")
    table.add_column("Run", style="cyan")
    table.add_column("Result", width=6)
    table.add_column("Turns", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Session Path", style="dim", overflow="fold")

    for entry in sorted(history, key=lambda x: x["run"]):
        success = entry.get("success", False)
        result = "[green]PASS[/green]" if success else "[red]FAIL[/red]"

        table.add_row(
            entry["run"],
            result,
            str(entry.get("turns", 0)),
            f"{entry.get('tokens', 0):,}",
            str(entry.get("session_path", ""))
        )

    console.print(table)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Browse evaluation results directory")
    parser.add_argument(
        "--dir",
        default="eval_results",
        help="Base directory to browse (default: eval_results)"
    )
    parser.add_argument(
        "--problem",
        help="Filter to specific problem name (partial match)"
    )
    parser.add_argument(
        "--history",
        metavar="PROBLEM_NAME",
        help="Show detailed history for a specific problem"
    )

    args = parser.parse_args()

    base_dir = Path(args.dir)
    console = Console()

    console.print(f"[bold]Browsing: {base_dir.absolute()}[/bold]\n")

    # Find all runs
    runs = find_all_runs(base_dir)

    if not runs:
        console.print("[yellow]No evaluation runs found[/yellow]")
        console.print(f"\nExpected structure:\n  {base_dir}/run_name/problem_name/session_id/")
        sys.exit(1)

    # Show history for specific problem or general summary
    if args.history:
        print_problem_details(runs, args.history, console)
    else:
        print_runs_summary(runs, console, problem_filter=args.problem)


if __name__ == "__main__":
    main()
