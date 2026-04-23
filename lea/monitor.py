"""Real-time monitoring dashboard for Lea agent sessions.

Usage:
    python -m lea.monitor                    # Monitor latest session
    python -m lea.monitor SESSION_ID         # Monitor specific session
    python -m lea.monitor --interval 1.0     # Custom refresh rate
"""

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .agent import SESSIONS_DIR


def find_latest_session() -> Path | None:
    """Find the most recently modified session file."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    sessions = sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return sessions[0] if sessions else None


def find_session_by_id(session_id: str) -> Path | None:
    """Find a session file by ID (exact match or prefix)."""
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


def load_session_safe(session_path: Path) -> dict | None:
    """Load session JSON, handling partial writes gracefully."""
    try:
        with open(session_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        # File is being written, partial JSON
        return None
    except Exception as e:
        return None


def count_turns(messages: list) -> int:
    """Count number of completed turns (assistant messages)."""
    return sum(1 for msg in messages if msg.get("role") == "assistant")


def analyze_tool_usage(messages: list) -> dict:
    """Extract tool call statistics from messages.

    Returns:
        {
            "tool_name": {
                "total": int,
                "errors": int,
                "last_call": timestamp_str or None
            }
        }
    """
    stats = defaultdict(lambda: {"total": 0, "errors": 0, "last_call": None})

    for i, msg in enumerate(messages):
        if msg.get("role") == "assistant" and isinstance(msg.get("content"), list):
            for part in msg["content"]:
                if part.get("type") == "tool_call":
                    tool_name = part.get("name")
                    stats[tool_name]["total"] += 1
                    stats[tool_name]["last_call"] = datetime.now(timezone.utc).isoformat()

                    # Check next message for error in result
                    if i + 1 < len(messages) and messages[i + 1].get("role") == "user":
                        for result_part in messages[i + 1].get("content", []):
                            if (result_part.get("type") == "tool_result" and
                                result_part.get("tool_name") == tool_name):
                                content = result_part.get("content", "")
                                if content.startswith("Error:"):
                                    stats[tool_name]["errors"] += 1

    return dict(stats)


def get_recent_tool_calls(messages: list, n: int = 10) -> list:
    """Get the N most recent tool calls with their results.

    Returns:
        List of {"tool": str, "args": dict, "result": str, "timestamp": str}
    """
    tool_calls = []

    for i, msg in enumerate(messages):
        if msg.get("role") == "assistant" and isinstance(msg.get("content"), list):
            for part in msg["content"]:
                if part.get("type") == "tool_call":
                    tool_name = part.get("name")
                    args = part.get("args", {})

                    # Find corresponding result
                    result = "(no result yet)"
                    if i + 1 < len(messages) and messages[i + 1].get("role") == "user":
                        for result_part in messages[i + 1].get("content", []):
                            if (result_part.get("type") == "tool_result" and
                                result_part.get("tool_name") == tool_name):
                                result = result_part.get("content", "")
                                break

                    tool_calls.append({
                        "tool": tool_name,
                        "args": args,
                        "result": result,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

    return tool_calls[-n:]


def get_last_assistant_text(messages: list) -> str:
    """Extract the last text output from the assistant."""
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and isinstance(msg.get("content"), list):
            text_parts = [p.get("text", "") for p in msg["content"] if p.get("type") == "text"]
            if text_parts:
                return "".join(text_parts)
    return "(no text output yet)"


def track_file_stats(file_path: str | Path) -> dict:
    """Get line count and sorry count for a .lean file.

    Returns:
        {"lines": int, "sorries": int, "path": str}
    """
    p = Path(file_path)
    if not p.exists():
        return {"lines": 0, "sorries": 0, "path": str(p)}

    try:
        content = p.read_text()
        lines = len(content.splitlines())
        sorries = len(re.findall(r'\bsorry\b', content))
        return {"lines": lines, "sorries": sorries, "path": str(p)}
    except Exception:
        return {"lines": 0, "sorries": 0, "path": str(p)}


def extract_active_files(messages: list) -> list[str]:
    """Extract file paths that are being actively worked on."""
    files = set()

    for msg in messages:
        if msg.get("role") == "assistant" and isinstance(msg.get("content"), list):
            for part in msg["content"]:
                if part.get("type") == "tool_call":
                    args = part.get("args", {})
                    # Extract 'path' argument from various tools
                    if "path" in args:
                        path = args["path"]
                        if path.endswith(".lean"):
                            files.add(path)

    return sorted(files)


def is_session_complete(messages: list) -> bool:
    """Check if session has completed (last assistant message has no tool calls)."""
    if not messages:
        return False

    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            content = msg.get("content", [])
            if isinstance(content, list):
                # Session is complete if last assistant message has no tool calls
                has_tool_calls = any(p.get("type") == "tool_call" for p in content)
                return not has_tool_calls
            return True  # Simple text response means done

    return False


def build_dashboard(session_data: dict, start_time: float) -> Layout:
    """Build the rich Layout dashboard."""
    layout = Layout()

    # Extract data
    session_id = session_data.get("id", "unknown")
    model = session_data.get("model", "unknown")
    messages = session_data.get("messages", [])
    usage = session_data.get("usage", {})

    turns = count_turns(messages)
    tool_stats = analyze_tool_usage(messages)
    recent_tools = get_recent_tool_calls(messages, n=6)
    last_text = get_last_assistant_text(messages)
    active_files = extract_active_files(messages)
    is_complete = is_session_complete(messages)

    elapsed = time.time() - start_time

    # Header
    status_color = "green" if is_complete else "yellow"
    status_text = "COMPLETE" if is_complete else "IN PROGRESS"

    header = Panel(
        f"[bold]{session_id}[/bold] | Model: {model} | Status: [{status_color}]{status_text}[/{status_color}] | Elapsed: {elapsed:.0f}s",
        style="bold blue",
    )

    # Status Panel (left)
    status_table = Table.grid(padding=(0, 2))
    status_table.add_column(style="cyan", justify="right")
    status_table.add_column()

    status_table.add_row("Turns:", f"[bold]{turns}[/bold]")
    status_table.add_row("Input tokens:", f"{usage.get('input_tokens', 0):,}")
    status_table.add_row("Output tokens:", f"{usage.get('output_tokens', 0):,}")

    if active_files:
        status_table.add_row("", "")
        status_table.add_row("[bold]Active Files:[/bold]", "")
        for file_path in active_files[:3]:  # Show first 3
            stats = track_file_stats(file_path)
            file_name = Path(file_path).name
            status_table.add_row(
                f"  {file_name}",
                f"{stats['lines']} lines, {stats['sorries']} sorries"
            )

    status_panel = Panel(status_table, title="Status", border_style="cyan")

    # Tool Stats Panel (right top)
    tool_table = Table(show_header=True, header_style="bold magenta", box=None)
    tool_table.add_column("Tool", style="cyan")
    tool_table.add_column("Calls", justify="right")
    tool_table.add_column("Errors", justify="right")

    # Sort by total calls
    sorted_tools = sorted(tool_stats.items(), key=lambda x: x[1]["total"], reverse=True)
    for tool_name, stats in sorted_tools[:8]:  # Top 8 tools
        error_style = "red" if stats["errors"] > 0 else ""
        tool_table.add_row(
            tool_name,
            str(stats["total"]),
            f"[{error_style}]{stats['errors']}[/{error_style}]" if stats["errors"] > 0 else "0"
        )

    tools_panel = Panel(tool_table, title="Tool Usage", border_style="magenta")

    # Recent Activity Panel (right bottom)
    activity_table = Table(show_header=False, box=None, padding=(0, 1))
    activity_table.add_column("Tool", style="yellow", width=15)
    activity_table.add_column("Args", style="dim", overflow="fold")

    for call in recent_tools:
        tool = call["tool"]
        # Format args compactly
        args_str = str(call["args"])[:50]
        if len(str(call["args"])) > 50:
            args_str += "..."

        activity_table.add_row(f"{tool}", args_str)

    activity_panel = Panel(activity_table, title="Recent Tool Calls", border_style="yellow")

    # Last Output Panel (bottom)
    last_output_preview = last_text[:400]
    if len(last_text) > 400:
        last_output_preview += "\n..."

    output_panel = Panel(
        Text(last_output_preview, style="dim"),
        title="Last Assistant Output",
        border_style="green",
    )

    # Layout structure
    layout.split_column(
        Layout(header, size=3),
        Layout(name="main"),
        Layout(output_panel, size=12),
    )

    layout["main"].split_row(
        Layout(status_panel, ratio=1),
        Layout(name="right", ratio=1),
    )

    layout["main"]["right"].split_column(
        Layout(tools_panel, ratio=1),
        Layout(activity_panel, ratio=1),
    )

    return layout


def monitor(session_id: str | None = None, interval: float = 2.0):
    """Monitor a Lea session in real-time.

    Args:
        session_id: Session ID to monitor (None = latest)
        interval: Refresh interval in seconds
    """
    # Find session
    if session_id:
        session_path = find_session_by_id(session_id)
        if not session_path:
            print(f"Error: Session '{session_id}' not found.", file=sys.stderr)
            sys.exit(1)
    else:
        session_path = find_latest_session()
        if not session_path:
            print("Error: No sessions found.", file=sys.stderr)
            sys.exit(1)

    print(f"Monitoring: {session_path.stem}")
    print(f"Refresh interval: {interval}s")
    print()

    console = Console()
    start_time = time.time()

    with Live(console=console, refresh_per_second=1) as live:
        while True:
            session_data = load_session_safe(session_path)

            if session_data:
                dashboard = build_dashboard(session_data, start_time)
                live.update(dashboard)

                # Check if complete
                if is_session_complete(session_data.get("messages", [])):
                    time.sleep(interval)  # One final refresh
                    break
            else:
                live.update(Panel(
                    "Waiting for session data...\n(File may be locked or incomplete)",
                    title="Loading",
                    border_style="yellow"
                ))

            time.sleep(interval)

    print("\n✓ Session complete.")


def main():
    parser = argparse.ArgumentParser(
        description="Monitor Lea agent sessions in real-time",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m lea.monitor                    # Monitor latest session
  python -m lea.monitor 20260423-143022    # Monitor specific session
  python -m lea.monitor --interval 1.0     # Custom refresh rate
        """
    )
    parser.add_argument(
        "session_id",
        nargs="?",
        help="Session ID to monitor (omit to monitor latest)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Refresh interval in seconds (default: 2.0)",
    )

    args = parser.parse_args()

    try:
        monitor(session_id=args.session_id, interval=args.interval)
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
