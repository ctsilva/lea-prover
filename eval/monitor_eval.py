"""Real-time monitoring dashboard for evaluation runs.

Usage:
    python -m eval.monitor_eval RESULTS_FILE.json     # Monitor specific eval
    python -m eval.monitor_eval --latest               # Monitor latest eval
    python -m eval.monitor_eval --interval 5.0         # Custom refresh rate
"""

import argparse
import json
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from rich.table import Table
from rich.text import Text


def find_latest_results() -> Path | None:
    """Find the most recent results JSON file."""
    results_dir = Path(__file__).parent / "results"
    if not results_dir.exists():
        return None

    json_files = [f for f in results_dir.glob("*.json") if not f.name.endswith("_transcripts")]
    if not json_files:
        return None

    return max(json_files, key=lambda p: p.stat().st_mtime)


def load_results_safe(path: Path) -> dict | None:
    """Load results JSON, handling partial writes."""
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, FileNotFoundError):
        return None


def calculate_stats(results: dict) -> dict:
    """Calculate aggregate statistics from results."""
    completed = results.get("completed", {})

    if not completed:
        return {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "pass_rate": 0.0,
            "avg_time": 0.0,
            "avg_turns": 0.0,
            "total_tokens": 0,
        }

    total = len(completed)
    passed = sum(1 for r in completed.values() if r.get("success"))
    failed = total - passed

    times = [r.get("time_s", 0) for r in completed.values()]
    avg_time = sum(times) / len(times) if times else 0

    turns = [r.get("turns", 0) for r in completed.values()]
    avg_turns = sum(turns) / len(turns) if turns else 0

    total_tokens = sum(
        r.get("usage", {}).get("input_tokens", 0) + r.get("usage", {}).get("output_tokens", 0)
        for r in completed.values()
    )

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": (passed / total * 100) if total else 0,
        "avg_time": avg_time,
        "avg_turns": avg_turns,
        "total_tokens": total_tokens,
    }


def get_recent_problems(results: dict, n: int = 5) -> list[dict]:
    """Get the N most recent problem results."""
    completed = results.get("completed", {})
    # Results are dict, so we'll just take the last N items
    # (assuming they're in insertion order, which they should be in modern Python)
    items = list(completed.items())[-n:]
    return [{"name": k, **v} for k, v in items]


def build_dashboard(results_data: dict, results_path: Path, start_time: float) -> Layout:
    """Build the Rich Layout dashboard for eval monitoring."""
    layout = Layout()

    # Extract data
    split = results_data.get("split", "unknown")
    model = results_data.get("model", "unknown")
    max_turns = results_data.get("max_turns", "?")

    stats = calculate_stats(results_data)
    recent = get_recent_problems(results_data, n=8)

    elapsed = time.time() - start_time

    # Header
    header = Panel(
        f"[bold]miniF2F Eval Monitor: {split} split[/bold]\n"
        f"Model: {model} | Max turns: {max_turns} | Elapsed: {elapsed:.0f}s",
        style="bold cyan",
    )

    # Progress Panel
    progress_table = Table.grid(padding=(0, 2))
    progress_table.add_column(style="cyan", justify="right")
    progress_table.add_column()

    progress_table.add_row("Problems:", f"[bold]{stats['total']}[/bold]")
    progress_table.add_row("Passed:", f"[green]{stats['passed']}[/green]")
    progress_table.add_row("Failed:", f"[red]{stats['failed']}[/red]")
    progress_table.add_row("Pass rate:", f"[bold]{stats['pass_rate']:.1f}%[/bold]")
    progress_table.add_row("", "")
    progress_table.add_row("Avg time:", f"{stats['avg_time']:.1f}s")
    progress_table.add_row("Avg turns:", f"{stats['avg_turns']:.1f}")
    progress_table.add_row("Total tokens:", f"{stats['total_tokens']:,}")

    progress_panel = Panel(progress_table, title="Progress", border_style="green")

    # Recent Problems Panel
    recent_table = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 1))
    recent_table.add_column("Problem", style="dim", width=25, overflow="fold")
    recent_table.add_column("Result", width=6)
    recent_table.add_column("Time", justify="right", width=6)
    recent_table.add_column("Turns", justify="right", width=5)

    for problem in recent:
        name = problem["name"]
        success = problem.get("success", False)
        time_s = problem.get("time_s", 0)
        turns = problem.get("turns", 0)

        result_display = "[green]PASS[/green]" if success else "[red]FAIL[/red]"

        recent_table.add_row(
            name[:25],
            result_display,
            f"{time_s:.0f}s",
            str(turns)
        )

    recent_panel = Panel(recent_table, title="Recent Problems", border_style="yellow")

    # Info Panel
    info_text = Text()
    info_text.append(f"Results file:\n", style="dim")
    info_text.append(f"{results_path.name}\n", style="cyan")
    info_text.append(f"\n", style="dim")
    info_text.append(f"Press Ctrl+C to exit", style="dim italic")

    info_panel = Panel(info_text, title="Info", border_style="blue")

    # Layout structure
    layout.split_column(
        Layout(header, size=4),
        Layout(name="main"),
        Layout(info_panel, size=6),
    )

    layout["main"].split_row(
        Layout(progress_panel, ratio=1),
        Layout(recent_panel, ratio=2),
    )

    return layout


def monitor(results_path: Path, interval: float = 2.0):
    """Monitor an evaluation run in real-time.

    Args:
        results_path: Path to results JSON file
        interval: Refresh interval in seconds
    """
    if not results_path.exists():
        print(f"Error: Results file not found: {results_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Monitoring: {results_path.name}")
    print(f"Refresh interval: {interval}s")
    print()

    console = Console()
    start_time = time.time()

    with Live(console=console, refresh_per_second=1) as live:
        while True:
            results_data = load_results_safe(results_path)

            if results_data:
                dashboard = build_dashboard(results_data, results_path, start_time)
                live.update(dashboard)

            time.sleep(interval)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Monitor miniF2F evaluation runs")
    parser.add_argument(
        "results_file",
        nargs="?",
        help="Path to results JSON file (omit to use --latest)",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Monitor the most recent eval results file",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Refresh interval in seconds (default: 2.0)",
    )

    args = parser.parse_args()

    # Determine which results file to monitor
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

    try:
        monitor(results_path=results_path, interval=args.interval)
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
