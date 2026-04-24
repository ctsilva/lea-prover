"""Session analysis tools for understanding agent behavior patterns.

Usage:
    python -m lea.analyze                    # Analyze latest session
    python -m lea.analyze SESSION_ID         # Analyze specific session
    python -m lea.analyze --export stats.json # Export to JSON
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from .agent import SESSIONS_DIR


def find_session_file(session_id: str | None = None) -> Path | None:
    """Find a session file by ID or get the latest."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    if session_id:
        # Try exact match
        exact_path = SESSIONS_DIR / f"{session_id}.json"
        if exact_path.exists():
            return exact_path

        # Try prefix match
        matches = [p for p in SESSIONS_DIR.glob("*.json") if p.stem.startswith(session_id)]
        if matches:
            return sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        return None
    else:
        # Get latest
        sessions = sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        return sessions[0] if sessions else None


def analyze_session(session_data: dict) -> dict:
    """Analyze a session and extract statistics.

    Returns:
        {
            "summary": {...},
            "tool_stats": {...},
            "temporal_patterns": {...},
            "errors": {...}
        }
    """
    messages = session_data.get("messages", [])
    session_id = session_data.get("id", "unknown")
    model = session_data.get("model", "unknown")
    usage = session_data.get("usage", {})

    # Count turns
    turns = sum(1 for msg in messages if msg.get("role") == "assistant")

    # Analyze tool usage
    tool_stats = defaultdict(lambda: {
        "total": 0,
        "errors": 0,
        "successes": 0,
        "durations_ms": []
    })

    # Track temporal patterns
    tools_by_turn = defaultdict(list)

    # Track errors
    error_messages = []

    current_turn = 0
    for i, msg in enumerate(messages):
        if msg.get("role") == "assistant":
            current_turn += 1

            if isinstance(msg.get("content"), list):
                for part in msg["content"]:
                    if part.get("type") == "tool_call":
                        tool_name = part.get("name")
                        tool_stats[tool_name]["total"] += 1
                        tools_by_turn[current_turn].append(tool_name)

                        # Check next message for result
                        if i + 1 < len(messages) and messages[i + 1].get("role") == "user":
                            for result_part in messages[i + 1].get("content", []):
                                if (result_part.get("type") == "tool_result" and
                                    result_part.get("tool_name") == tool_name):
                                    content = result_part.get("content", "")

                                    if content.startswith("Error:"):
                                        tool_stats[tool_name]["errors"] += 1
                                        error_messages.append({
                                            "turn": current_turn,
                                            "tool": tool_name,
                                            "error": content[:200]
                                        })
                                    else:
                                        tool_stats[tool_name]["successes"] += 1

    # Calculate success rates
    for tool_name, stats in tool_stats.items():
        if stats["total"] > 0:
            stats["success_rate"] = stats["successes"] / stats["total"]
        else:
            stats["success_rate"] = 0.0

    # Identify most common error patterns
    error_patterns = defaultdict(int)
    for err in error_messages:
        # Extract error type (first line of error message)
        error_type = err["error"].split("\n")[0]
        error_patterns[error_type] += 1

    # Find tool usage patterns
    common_sequences = []
    for turn, tools in tools_by_turn.items():
        if len(tools) >= 2:
            sequence = " -> ".join(tools)
            common_sequences.append(sequence)

    # Count sequence frequencies
    sequence_counts = defaultdict(int)
    for seq in common_sequences:
        sequence_counts[seq] += 1

    top_sequences = sorted(sequence_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "summary": {
            "session_id": session_id,
            "model": model,
            "turns": turns,
            "total_tools_used": sum(stats["total"] for stats in tool_stats.values()),
            "unique_tools": len(tool_stats),
            "total_errors": sum(stats["errors"] for stats in tool_stats.values()),
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        },
        "tool_stats": dict(tool_stats),
        "temporal_patterns": {
            "tools_by_turn": dict(tools_by_turn),
            "common_sequences": top_sequences,
        },
        "errors": {
            "total": len(error_messages),
            "by_turn": error_messages,
            "common_patterns": dict(sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)[:10])
        }
    }


def print_analysis(stats: dict, console: Console):
    """Print formatted analysis to console."""

    summary = stats["summary"]
    tool_stats = stats["tool_stats"]
    temporal = stats["temporal_patterns"]
    errors = stats["errors"]

    # Header
    console.print(Panel(
        f"[bold]Session Analysis: {summary['session_id']}[/bold]\n"
        f"Model: {summary['model']} | Turns: {summary['turns']} | Tools Used: {summary['total_tools_used']}",
        style="bold cyan"
    ))
    console.print()

    # Summary Stats
    summary_table = Table(title="Summary Statistics", show_header=True, header_style="bold magenta")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", justify="right")

    summary_table.add_row("Total Turns", str(summary["turns"]))
    summary_table.add_row("Total Tool Calls", str(summary["total_tools_used"]))
    summary_table.add_row("Unique Tools", str(summary["unique_tools"]))
    summary_table.add_row("Total Errors", str(summary["total_errors"]))
    summary_table.add_row("Input Tokens", f"{summary['input_tokens']:,}")
    summary_table.add_row("Output Tokens", f"{summary['output_tokens']:,}")
    summary_table.add_row("Total Tokens", f"{summary['total_tokens']:,}")

    if summary["total_tools_used"] > 0:
        error_rate = (summary["total_errors"] / summary["total_tools_used"]) * 100
        summary_table.add_row("Error Rate", f"{error_rate:.1f}%")

    console.print(summary_table)
    console.print()

    # Tool Usage Stats
    tool_table = Table(title="Tool Usage Statistics", show_header=True, header_style="bold green")
    tool_table.add_column("Tool", style="cyan")
    tool_table.add_column("Calls", justify="right")
    tool_table.add_column("Success", justify="right")
    tool_table.add_column("Errors", justify="right")
    tool_table.add_column("Success Rate", justify="right")

    sorted_tools = sorted(tool_stats.items(), key=lambda x: x[1]["total"], reverse=True)
    for tool_name, stats in sorted_tools:
        success_rate = stats["success_rate"] * 100
        success_color = "green" if success_rate >= 90 else "yellow" if success_rate >= 70 else "red"

        tool_table.add_row(
            tool_name,
            str(stats["total"]),
            str(stats["successes"]),
            f"[red]{stats['errors']}[/red]" if stats["errors"] > 0 else "0",
            f"[{success_color}]{success_rate:.0f}%[/{success_color}]"
        )

    console.print(tool_table)
    console.print()

    # Common Tool Sequences
    if temporal["common_sequences"]:
        seq_table = Table(title="Common Tool Sequences", show_header=True, header_style="bold yellow")
        seq_table.add_column("Sequence", style="dim")
        seq_table.add_column("Count", justify="right")

        for sequence, count in temporal["common_sequences"]:
            seq_table.add_row(sequence, str(count))

        console.print(seq_table)
        console.print()

    # Error Analysis
    if errors["total"] > 0:
        error_table = Table(title="Error Analysis", show_header=True, header_style="bold red")
        error_table.add_column("Error Pattern", style="dim")
        error_table.add_column("Count", justify="right")

        for pattern, count in list(errors["common_patterns"].items())[:10]:
            error_table.add_row(pattern[:80], str(count))

        console.print(error_table)
        console.print()

        # Show recent errors
        console.print("[bold]Recent Errors:[/bold]")
        for err in errors["by_turn"][-5:]:
            console.print(f"  Turn {err['turn']} - {err['tool']}: [dim]{err['error']}[/dim]")
        console.print()


def main():
    """CLI entry point for session analysis."""
    parser = argparse.ArgumentParser(description="Analyze Lea agent sessions")
    parser.add_argument("session_id", nargs="?", help="Session ID to analyze (default: latest)")
    parser.add_argument("--export", metavar="FILE", help="Export analysis to JSON file")

    args = parser.parse_args()

    # Find session
    session_file = find_session_file(args.session_id)
    if not session_file:
        if args.session_id:
            print(f"Error: Session '{args.session_id}' not found.", file=sys.stderr)
        else:
            print("Error: No sessions found.", file=sys.stderr)
        sys.exit(1)

    # Load session
    try:
        session_data = json.loads(session_file.read_text())
    except json.JSONDecodeError:
        print(f"Error: Could not parse session file: {session_file}", file=sys.stderr)
        sys.exit(1)

    # Analyze
    stats = analyze_session(session_data)

    # Export to JSON if requested
    if args.export:
        export_path = Path(args.export)
        export_path.write_text(json.dumps(stats, indent=2))
        print(f"Analysis exported to: {export_path}")

    # Print to console
    console = Console()
    print_analysis(stats, console)


if __name__ == "__main__":
    main()
