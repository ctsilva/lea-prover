"""Enhanced session management tools for exploring and managing session history.

Usage:
    python -m lea.session_manager list                          # List all sessions
    python -m lea.session_manager list --model gpt-5.4          # Filter by model
    python -m lea.session_manager compare SESSION_ID1 SESSION_ID2  # Compare sessions
    python -m lea.session_manager cleanup --failed              # Delete failed sessions
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .agent import SESSIONS_DIR, MODEL_PRICING, DEFAULT_PRICING


def load_session(session_path: Path) -> dict | None:
    """Load a session JSON file."""
    try:
        return json.loads(session_path.read_text())
    except:
        return None


def find_session_by_id(session_id: str) -> Path | None:
    """Find a session file by ID (exact or prefix match)."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    # Try exact match
    exact_path = SESSIONS_DIR / f"{session_id}.json"
    if exact_path.exists():
        return exact_path

    # Try prefix match
    matches = [p for p in SESSIONS_DIR.glob("*.json") if p.stem.startswith(session_id)]
    if matches:
        return sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)[0]

    return None


def is_session_successful(session_data: dict) -> bool | None:
    """Determine if a session completed successfully.

    Returns:
        True if successful, False if failed, None if unknown
    """
    messages = session_data.get("messages", [])
    if not messages:
        return None

    # Check if last assistant message has no tool calls (completed)
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            content = msg.get("content", [])
            if isinstance(content, list):
                has_tool_calls = any(p.get("type") == "tool_call" for p in content)
                # If no tool calls, likely completed successfully
                if not has_tool_calls:
                    # Check if there are any errors in the last text
                    text_parts = [p.get("text", "") for p in content if p.get("type") == "text"]
                    text = "".join(text_parts).lower()
                    if "error" in text or "failed" in text:
                        return False
                    return True
                return False  # Still has tool calls, didn't complete

    return None


def get_active_files(session_data: dict) -> list[str]:
    """Extract files that were actively worked on."""
    files = set()
    messages = session_data.get("messages", [])

    for msg in messages:
        if msg.get("role") == "assistant" and isinstance(msg.get("content"), list):
            for part in msg["content"]:
                if part.get("type") == "tool_call":
                    args = part.get("args", {})
                    if "path" in args and args["path"].endswith(".lean"):
                        files.add(Path(args["path"]).name)

    return sorted(files)


def calculate_cost(usage: dict, model: str) -> float:
    """Calculate estimated cost in USD."""
    price_in, price_out = MODEL_PRICING.get(model, DEFAULT_PRICING)
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


def list_sessions_enhanced(
    model_filter: str | None = None,
    status_filter: str | None = None,
    limit: int = 20
) -> list[dict]:
    """List sessions with enhanced information.

    Args:
        model_filter: Filter by model name
        status_filter: Filter by status ("success", "failed", "unknown")
        limit: Maximum number of sessions to return

    Returns:
        List of session summary dicts
    """
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    sessions = sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    summaries = []
    for path in sessions:
        data = load_session(path)
        if not data:
            continue

        # Apply filters
        if model_filter and data.get("model", "") != model_filter:
            continue

        success = is_session_successful(data)
        status = "success" if success else "failed" if success is False else "unknown"

        if status_filter and status != status_filter:
            continue

        # Extract info
        messages = data.get("messages", [])
        task = messages[0]["content"] if messages else ""
        if isinstance(task, str) and len(task) > 60:
            task = task[:60] + "..."

        usage = data.get("usage", {})
        model = data.get("model", "unknown")

        summaries.append({
            "id": data.get("id", path.stem),
            "timestamp": data.get("timestamp", ""),
            "model": model,
            "task": task,
            "turns": len([m for m in messages if m["role"] == "assistant"]),
            "status": status,
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            "cost": calculate_cost(usage, model),
            "active_files": get_active_files(data),
        })

        if len(summaries) >= limit:
            break

    return summaries


def compare_sessions(session_id1: str, session_id2: str) -> dict:
    """Compare two sessions side-by-side.

    Returns:
        Dict with comparison metrics
    """
    path1 = find_session_by_id(session_id1)
    path2 = find_session_by_id(session_id2)

    if not path1:
        raise ValueError(f"Session not found: {session_id1}")
    if not path2:
        raise ValueError(f"Session not found: {session_id2}")

    data1 = load_session(path1)
    data2 = load_session(path2)

    # Analyze tool usage for both
    def analyze_tools(messages):
        tools = {}
        for msg in messages:
            if msg.get("role") == "assistant" and isinstance(msg.get("content"), list):
                for part in msg["content"]:
                    if part.get("type") == "tool_call":
                        tool = part.get("name")
                        tools[tool] = tools.get(tool, 0) + 1
        return tools

    return {
        "session1": {
            "id": data1.get("id"),
            "model": data1.get("model"),
            "turns": len([m for m in data1["messages"] if m["role"] == "assistant"]),
            "tokens": data1.get("usage", {}).get("input_tokens", 0) + data1.get("usage", {}).get("output_tokens", 0),
            "cost": calculate_cost(data1.get("usage", {}), data1.get("model", "")),
            "tools": analyze_tools(data1.get("messages", [])),
            "status": "success" if is_session_successful(data1) else "failed",
        },
        "session2": {
            "id": data2.get("id"),
            "model": data2.get("model"),
            "turns": len([m for m in data2["messages"] if m["role"] == "assistant"]),
            "tokens": data2.get("usage", {}).get("input_tokens", 0) + data2.get("usage", {}).get("output_tokens", 0),
            "cost": calculate_cost(data2.get("usage", {}), data2.get("model", "")),
            "tools": analyze_tools(data2.get("messages", [])),
            "status": "success" if is_session_successful(data2) else "failed",
        }
    }


def cleanup_sessions(failed_only: bool = False, dry_run: bool = True) -> list[str]:
    """Delete sessions based on criteria.

    Args:
        failed_only: Only delete failed sessions
        dry_run: If True, just report what would be deleted

    Returns:
        List of deleted (or would-be deleted) session IDs
    """
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    sessions = list(SESSIONS_DIR.glob("*.json"))

    to_delete = []
    for path in sessions:
        data = load_session(path)
        if not data:
            continue

        if failed_only:
            success = is_session_successful(data)
            if success is False:  # Only delete confirmed failures
                to_delete.append(path)
        else:
            to_delete.append(path)

    deleted_ids = []
    for path in to_delete:
        deleted_ids.append(path.stem)
        if not dry_run:
            path.unlink()

    return deleted_ids


def print_session_list(summaries: list[dict], console: Console):
    """Print formatted session list."""
    table = Table(title=f"Sessions ({len(summaries)})", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim", width=16)
    table.add_column("Model", style="cyan", width=12)
    table.add_column("Status", width=8)
    table.add_column("Turns", justify="right", width=6)
    table.add_column("Tokens", justify="right", width=10)
    table.add_column("Cost", justify="right", width=8)
    table.add_column("Task", style="dim", overflow="fold")

    for s in summaries:
        # Color code status
        status = s["status"]
        if status == "success":
            status_display = "[green]✓[/green]"
        elif status == "failed":
            status_display = "[red]✗[/red]"
        else:
            status_display = "[yellow]?[/yellow]"

        table.add_row(
            s["id"][:16],
            s["model"][:12],
            status_display,
            str(s["turns"]),
            f"{s['total_tokens']:,}",
            f"${s['cost']:.3f}",
            s["task"],
        )

    console.print(table)


def print_comparison(comparison: dict, console: Console):
    """Print session comparison."""
    s1 = comparison["session1"]
    s2 = comparison["session2"]

    console.print(Panel(
        f"[bold]Comparing Sessions[/bold]\n"
        f"{s1['id']} vs {s2['id']}",
        style="cyan"
    ))
    console.print()

    # Summary comparison
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric")
    table.add_column(s1["id"][:16], justify="right")
    table.add_column(s2["id"][:16], justify="right")
    table.add_column("Difference", justify="right")

    table.add_row("Model", s1["model"], s2["model"], "")
    table.add_row("Status", s1["status"], s2["status"], "")
    table.add_row("Turns", str(s1["turns"]), str(s2["turns"]),
                  f"{s2['turns'] - s1['turns']:+d}")
    table.add_row("Tokens", f"{s1['tokens']:,}", f"{s2['tokens']:,}",
                  f"{s2['tokens'] - s1['tokens']:+,}")
    table.add_row("Cost", f"${s1['cost']:.3f}", f"${s2['cost']:.3f}",
                  f"${s2['cost'] - s1['cost']:+.3f}")

    console.print(table)
    console.print()

    # Tool usage comparison
    all_tools = set(s1["tools"].keys()) | set(s2["tools"].keys())
    if all_tools:
        tool_table = Table(title="Tool Usage", show_header=True, header_style="bold green")
        tool_table.add_column("Tool", style="cyan")
        tool_table.add_column(s1["id"][:16], justify="right")
        tool_table.add_column(s2["id"][:16], justify="right")

        for tool in sorted(all_tools):
            count1 = s1["tools"].get(tool, 0)
            count2 = s2["tools"].get(tool, 0)
            tool_table.add_row(tool, str(count1), str(count2))

        console.print(tool_table)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Manage Lea agent sessions")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # List command
    list_parser = subparsers.add_parser("list", help="List sessions")
    list_parser.add_argument("--model", help="Filter by model name")
    list_parser.add_argument("--status", choices=["success", "failed", "unknown"],
                            help="Filter by status")
    list_parser.add_argument("--limit", type=int, default=20, help="Maximum sessions to show")

    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare two sessions")
    compare_parser.add_argument("session1", help="First session ID")
    compare_parser.add_argument("session2", help="Second session ID")

    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Delete sessions")
    cleanup_parser.add_argument("--failed", action="store_true", help="Only delete failed sessions")
    cleanup_parser.add_argument("--confirm", action="store_true", help="Actually delete (not dry run)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    console = Console()

    if args.command == "list":
        summaries = list_sessions_enhanced(
            model_filter=args.model,
            status_filter=args.status,
            limit=args.limit
        )
        print_session_list(summaries, console)

    elif args.command == "compare":
        try:
            comparison = compare_sessions(args.session1, args.session2)
            print_comparison(comparison, console)
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)

    elif args.command == "cleanup":
        deleted = cleanup_sessions(failed_only=args.failed, dry_run=not args.confirm)

        if args.confirm:
            console.print(f"[green]Deleted {len(deleted)} sessions[/green]")
        else:
            console.print(f"[yellow]Would delete {len(deleted)} sessions (use --confirm to actually delete)[/yellow]")

        for session_id in deleted:
            console.print(f"  - {session_id}")


if __name__ == "__main__":
    main()
