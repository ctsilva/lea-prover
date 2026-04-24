"""Incremental result tracking and logging for Lea sessions.

This module provides utilities for logging session progress in real-time,
enabling monitoring and analysis of running sessions.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path


class ResultTracker:
    """Tracks and logs session progress incrementally."""

    def __init__(self, result_dir: Path | None, session_id: str, workspace_dir: Path | None = None):
        """Initialize result tracker.

        Args:
            result_dir: Base directory for results (e.g., "results/")
            session_id: Unique session identifier
            workspace_dir: Path to workspace directory (for snapshots)
        """
        self.result_dir = result_dir
        self.session_id = session_id
        self.session_result_dir = None
        self.snapshot_manager = None

        if result_dir:
            self.session_result_dir = Path(result_dir) / session_id
            self.session_result_dir.mkdir(parents=True, exist_ok=True)

            # Initialize snapshot manager if workspace provided
            if workspace_dir:
                from .snapshots import SnapshotManager
                self.snapshot_manager = SnapshotManager(result_dir, session_id, workspace_dir)

    def log_metadata(self, task: str, model: str, config: dict, system_prompt: str | None = None):
        """Log session metadata at start.

        Args:
            task: The task description
            model: Model name
            config: Additional configuration (max_turns, prompt_variant, etc.)
            system_prompt: The full system prompt (optional but recommended)
        """
        if not self.session_result_dir:
            return

        metadata = {
            "session_id": self.session_id,
            "task": task,
            "model": model,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "config": config,
        }

        if system_prompt:
            metadata["system_prompt"] = system_prompt

        metadata_file = self.session_result_dir / "metadata.json"
        metadata_file.write_text(json.dumps(metadata, indent=2))

    def log_tool_call(self, turn: int, tool_name: str, args: dict, result: str, duration_ms: float | None = None):
        """Log a single tool call to the timeline.

        Args:
            turn: Current turn number
            tool_name: Name of the tool
            args: Tool arguments
            result: Tool result (truncated if too long)
            duration_ms: Execution time in milliseconds (optional)
        """
        if not self.session_result_dir:
            return

        timeline_file = self.session_result_dir / "tool_timeline.jsonl"

        # Truncate long results
        result_preview = result[:500] if len(result) > 500 else result

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "turn": turn,
            "tool": tool_name,
            "args": args,
            "result_preview": result_preview,
        }

        if duration_ms is not None:
            entry["duration_ms"] = duration_ms

        # Append as JSONL (one JSON object per line)
        with open(timeline_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def log_turn_summary(self, turn: int, tool_calls: list, text_output: str, duration_s: float):
        """Log a summary of a completed turn.

        Args:
            turn: Turn number
            tool_calls: List of {"name": str, "args": dict, "result": str}
            text_output: Combined text output from assistant
            duration_s: Turn duration in seconds
        """
        if not self.session_result_dir:
            return

        summary = {
            "turn": turn,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_s": round(duration_s, 2),
            "tool_calls": [
                {
                    "tool": tc["name"],
                    "args": tc["args"],
                    "result_preview": tc["result"][:200] if len(tc["result"]) > 200 else tc["result"],
                }
                for tc in tool_calls
            ],
            "text_output": text_output[:1000] if len(text_output) > 1000 else text_output,
        }

        turn_file = self.session_result_dir / f"turn_{turn}.json"
        turn_file.write_text(json.dumps(summary, indent=2))

    def log_final_result(self, turns: int, usage: dict, success: bool = False, error: str | None = None):
        """Log final session result.

        Args:
            turns: Total turns completed
            usage: Token usage {"input_tokens": int, "output_tokens": int}
            success: Whether task completed successfully
            error: Error message if failed
        """
        if not self.session_result_dir:
            return

        result = {
            "session_id": self.session_id,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "turns": turns,
            "usage": usage,
            "success": success,
            "error": error,
        }

        result_file = self.session_result_dir / "final_result.json"
        result_file.write_text(json.dumps(result, indent=2))

    def capture_file_snapshot(self, turn: int, modified_files: list[str]):
        """Capture snapshot of files modified in this turn.

        Args:
            turn: Current turn number
            modified_files: List of file paths that were modified
        """
        if self.snapshot_manager:
            self.snapshot_manager.capture_intermediate_snapshot(turn, modified_files)

    def capture_before_snapshot(self):
        """Capture initial workspace state."""
        if self.snapshot_manager:
            return self.snapshot_manager.capture_before_snapshot()
        return {}

    def capture_after_snapshot(self):
        """Capture final workspace state and compute diff."""
        if self.snapshot_manager:
            return self.snapshot_manager.capture_after_snapshot()
        return {}


def track_file_stats(file_path: str | Path) -> dict:
    """Get line count and sorry count for a .lean file.

    Args:
        file_path: Path to .lean file

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


def extract_files_from_args(args: dict) -> list[str]:
    """Extract file paths from tool arguments.

    Args:
        args: Tool arguments dictionary

    Returns:
        List of file paths found in arguments
    """
    files = []
    if "path" in args and isinstance(args["path"], str):
        files.append(args["path"])
    return files
