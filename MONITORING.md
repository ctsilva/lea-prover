# Real-Time Monitoring for Lea Agent

This document describes the observability and monitoring features added to Lea, enabling real-time tracking of agent behavior during long-running sessions.

## Quick Start

### 1. Run a Session with Result Tracking

Enable result tracking by adding `--result-dir` to your Lea command:

```bash
lea "Prove that 1 + 1 = 2 in Lean 4" \
    --result-dir results \
    --max-turns 20
```

This creates a directory structure like:
```
results/
└── 20260423-143022/        # Session ID (timestamp)
    ├── metadata.json       # Task, model, config
    ├── tool_timeline.jsonl # Real-time tool call log
    ├── turn_1.json         # Turn 1 summary
    ├── turn_2.json         # Turn 2 summary
    └── final_result.json   # Final summary with usage stats
```

### 2. Monitor in Real-Time

While the agent is running, open another terminal and run:

```bash
python -m lea.monitor
```

This shows a live dashboard with:
- Current turn and elapsed time
- Tool usage statistics (how many times each tool was called)
- Recent tool calls with arguments
- Last assistant text output
- File statistics (line counts, sorry counts)
- Token usage

The monitor auto-updates every 2 seconds and exits when the session completes.

### 3. Monitor a Specific Session

```bash
# By session ID
python -m lea.monitor 20260423-143022

# By partial ID (prefix match)
python -m lea.monitor 202604

# Custom refresh rate (1 second)
python -m lea.monitor --interval 1.0
```

## Features

### Incremental Result Logging

When `--result-dir` is enabled, Lea logs progress **immediately** as it happens:

1. **`metadata.json`** - Written at session start
   - Task description
   - Model name and configuration
   - Start timestamp

2. **`tool_timeline.jsonl`** - Appended after each tool call
   - JSONL format (one JSON object per line)
   - Timestamp, turn number, tool name, args, result preview
   - Tool execution duration in milliseconds

3. **`turn_N.json`** - Written after each turn completes
   - All tool calls in that turn
   - Text output from assistant
   - Turn duration

4. **`final_result.json`** - Written when session ends
   - Total turns completed
   - Token usage (input/output)
   - Success/failure status

### Real-Time Dashboard

The monitoring dashboard (`lea.monitor`) provides:

#### Status Panel
- Session ID and model
- Current turn number
- Total elapsed time
- Token counts (input/output)
- Active files being edited with stats

#### Tool Usage Panel
- Tool names sorted by frequency
- Total calls per tool
- Error counts per tool

#### Recent Activity Panel
- Last 6 tool calls
- Tool arguments (truncated)
- Shows what the agent is currently doing

#### Output Preview Panel
- Last text output from the assistant
- Truncated to fit terminal

### File Statistics Tracking

For `.lean` files being worked on, the monitor shows:
- **Line count** - Total lines in file
- **Sorry count** - Number of `sorry` placeholders remaining

This helps track proof completion progress.

## Usage Examples

### Example 1: Monitor a Long Benchmark Run

Terminal 1 - Run evaluation:
```bash
python -m eval.run_minif2f \
    --split valid \
    --limit 10 \
    --result-dir eval_results
```

Terminal 2 - Monitor current problem:
```bash
# Monitors the latest session (current problem being solved)
python -m lea.monitor
```

### Example 2: Custom Refresh Rate

For faster updates during debugging:
```bash
python -m lea.monitor --interval 0.5  # Update every 500ms
```

### Example 3: Analyze Completed Sessions

Even without enabling `--result-dir` during the run, you can still analyze sessions from the session history:

```bash
# List all sessions
lea --sessions

# Monitor a past session (reads from ~/.lea/sessions/)
python -m lea.monitor 20260423-143022
```

Note: Past sessions only show the final state, not incremental progress. Use `--result-dir` during the run for real-time monitoring.

## Integration with Eval Scripts

All eval scripts support `--result-dir` for per-problem tracking:

```bash
python -m eval.run_minif2f \
    --split valid \
    --result-dir eval_results/minif2f_run1

python -m eval.run_fqb \
    --result-dir eval_results/fqb_run1
```

This creates a subdirectory per problem with full incremental logs.

## Data Formats

### metadata.json
```json
{
  "session_id": "20260423-143022",
  "task": "Prove that 1 + 1 = 2 in Lean 4",
  "model": "gemini-3.1-pro-preview",
  "started_at": "2026-04-23T14:30:22.123456Z",
  "config": {
    "max_turns": 20,
    "prompt_variant": "default",
    "provider": "gemini"
  }
}
```

### tool_timeline.jsonl
```jsonl
{"timestamp": "2026-04-23T14:30:25.123Z", "turn": 1, "tool": "read_file", "args": {"path": "workspace/test.lean"}, "result_preview": "Error: workspace/test.lean does not exist.", "duration_ms": 2.3}
{"timestamp": "2026-04-23T14:30:28.456Z", "turn": 1, "tool": "write_file", "args": {"path": "workspace/test.lean", "content": "..."}, "result_preview": "Wrote 234 bytes to workspace/test.lean", "duration_ms": 15.7}
{"timestamp": "2026-04-23T14:30:35.789Z", "turn": 1, "tool": "lean_check", "args": {"path": "workspace/test.lean"}, "result_preview": "OK — no errors, no warnings.", "duration_ms": 1234.5}
```

### turn_N.json
```json
{
  "turn": 1,
  "timestamp": "2026-04-23T14:30:36.000Z",
  "duration_s": 13.5,
  "tool_calls": [
    {
      "tool": "write_file",
      "args": {"path": "workspace/test.lean", "content": "..."},
      "result_preview": "Wrote 234 bytes to workspace/test.lean"
    },
    {
      "tool": "lean_check",
      "args": {"path": "workspace/test.lean"},
      "result_preview": "OK — no errors, no warnings."
    }
  ],
  "text_output": "I'll write a simple proof that 1 + 1 = 2..."
}
```

### final_result.json
```json
{
  "session_id": "20260423-143022",
  "completed_at": "2026-04-23T14:32:15.000Z",
  "turns": 3,
  "usage": {
    "input_tokens": 12450,
    "output_tokens": 3820
  },
  "success": true,
  "error": null
}
```

## Performance

The incremental logging adds minimal overhead:
- **File writes**: Asynchronous, non-blocking
- **JSON serialization**: Only truncated data (previews)
- **Impact**: < 1% slowdown in typical sessions

The monitor reads files periodically (default 2s) and does not impact the running agent.

## Troubleshooting

### Monitor shows "Waiting for session data..."

This means:
- Session file is being written (partial JSON)
- Session hasn't started yet
- File permissions issue

Wait a few seconds for the session to initialize.

### No session found

```bash
# Check if any sessions exist
lea --sessions

# Check result directory
ls -la results/
```

If using `--result-dir`, the monitor reads from `~/.lea/sessions/` (standard session storage), not the result directory. The result directory contains the incremental logs for analysis, while the session file is used for monitoring.

### Monitor not updating

- Check that the agent is still running
- Verify the session file exists: `~/.lea/sessions/SESSION_ID.json`
- Try increasing refresh rate: `--interval 1.0`

### Tool timeline file is too large

The timeline is append-only and can grow large for long sessions. Each line is ~200 bytes, so:
- 1,000 tool calls ≈ 200 KB
- 10,000 tool calls ≈ 2 MB

This is typically fine. For analysis, you can filter with standard tools:

```bash
# Get only lean_check calls
grep '"tool": "lean_check"' tool_timeline.jsonl

# Count tool calls by type
jq -r .tool tool_timeline.jsonl | sort | uniq -c
```

## Future Enhancements

See [OBSERVABILITY_PLAN.md](OBSERVABILITY_PLAN.md) for the complete roadmap. Upcoming features include:

- **HTML visualizations** - Interactive post-hoc reports
- **Snapshot system** - Compare before/after file states
- **Comparative analysis** - Compare multiple sessions
- **Eval-specific monitoring** - Track progress across entire benchmark runs

## Credits

Inspired by the [numina-lean-agent tracking system](../numina-lean-agent/AGENT_TRACKING_GUIDE.md).

---

**Last Updated**: 2026-04-23
