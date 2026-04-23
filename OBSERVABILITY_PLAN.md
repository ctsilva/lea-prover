# Lea Agent Observability Implementation Plan

## Overview

This plan outlines enhancements to make Lea's behavior easier to understand, especially during long-running jobs. The goal is to provide real-time visibility into agent execution, structured result storage, and post-hoc analysis capabilities.

**Inspired by**: [numina-lean-agent tracking system](../numina-lean-agent/AGENT_TRACKING_GUIDE.md)

**Key constraint**: Lea does not use MCP and has a simpler architecture - adaptations must fit this design.

---

## Priority Levels

- **P0 (Critical)**: Core real-time observability - must have for long-running jobs
- **P1 (High)**: Essential for understanding agent behavior and debugging
- **P2 (Medium)**: Nice-to-have improvements for analysis and comparison
- **P3 (Low)**: Future enhancements, polish, and advanced features

---

## Phase 1: Core Real-Time Observability

### P0: Real-Time Monitoring Dashboard
**Purpose**: See what the agent is doing right now without waiting for completion

**Tasks**:
- [ ] Create `lea/monitor.py` with basic dashboard
  - [ ] Auto-detect latest session or accept session ID
  - [ ] Poll session JSON file every 2 seconds (configurable)
  - [ ] Display current turn number and elapsed time
  - [ ] Show tool call counts (read_file, write_file, lean_check, etc.)
  - [ ] Display last 5-10 tool calls with timestamps
  - [ ] Show last assistant text output (truncated)
  - [ ] Auto-exit when session completes
- [ ] Use `rich` library for formatted terminal output
  - [ ] Status panel (top): session ID, model, turn, duration
  - [ ] Tool stats panel (left): tool names and counts
  - [ ] Recent activity panel (right): last N tool calls
  - [ ] Text preview panel (bottom): latest agent output
- [ ] Add CLI entry point: `python -m lea.monitor [session_id]`
- [ ] Handle edge cases:
  - [ ] Session file doesn't exist yet
  - [ ] Session file is being written (partial JSON)
  - [ ] Multiple concurrent sessions

**Files to create**:
- `lea/monitor.py` (~200-300 lines)

**Dependencies**:
- `rich` (already used in numina agent)

**Estimated effort**: 4-6 hours

---

### P0: Incremental Result Logging
**Purpose**: Write progress data immediately so monitoring can work during long turns

**Tasks**:
- [ ] Add `result_dir` parameter to `run()` function (optional)
- [ ] Create result directory structure: `results/{session_id}/`
- [ ] Log tool calls immediately to `tool_timeline.jsonl`
  - [ ] One JSON line per tool execution
  - [ ] Fields: `timestamp`, `turn`, `tool_name`, `args`, `result_preview`, `duration_ms`
- [ ] Save turn summaries to `turn_N.json` after each turn
  - [ ] Tool calls made
  - [ ] Text output
  - [ ] Timestamp and duration
- [ ] Save session metadata to `metadata.json` at start
  - [ ] Task description
  - [ ] Model name
  - [ ] Start timestamp
  - [ ] Configuration (max_turns, prompt_variant)
- [ ] Update final result summary at end: `final_result.json`
  - [ ] Success/failure
  - [ ] Total turns
  - [ ] Total tokens and estimated cost
  - [ ] Final verification status (if applicable)

**Files to modify**:
- `lea/agent.py` (add ~50-80 lines)

**Files to create**:
- Helper functions in new file or within `agent.py`

**Estimated effort**: 3-4 hours

---

### P1: File Statistics Tracking
**Purpose**: Monitor proof progress (line counts, sorry counts)

**Tasks**:
- [ ] Create `track_file_stats()` function
  - [ ] Count total lines in .lean file
  - [ ] Count `sorry` occurrences (regex: `\bsorry\b`)
  - [ ] Return `{"lines": int, "sorries": int, "path": str}`
- [ ] Integrate into monitoring dashboard
  - [ ] Show current stats for files being worked on
  - [ ] Show delta from initial snapshot (if available)
  - [ ] Color-code: green if sorries decreasing, red if increasing
- [ ] Track which files are being actively modified
  - [ ] Parse tool calls to identify target files
  - [ ] Maintain list of "active files" per session
- [ ] Add to incremental logging
  - [ ] Log file stats after each write_file/edit_file call
  - [ ] Include in turn summaries

**Files to create/modify**:
- Add to `lea/monitor.py` (~30-50 lines)
- Add helper in `lea/utils.py` or `lea/tracking.py` (~40 lines)

**Estimated effort**: 2-3 hours

---

## Phase 2: Enhanced Analysis & Debugging

### P1: Tool Usage Statistics
**Purpose**: Understand patterns in how agent uses tools

**Tasks**:
- [ ] Create `analyze_session()` function
  - [ ] Parse session messages to extract all tool calls
  - [ ] Count by tool name
  - [ ] Detect errors (tool results starting with "Error:")
  - [ ] Calculate success rates per tool
  - [ ] Track temporal patterns (which tools used when)
- [ ] Generate statistics report
  - [ ] Total calls by tool type
  - [ ] Success vs error rates
  - [ ] Average duration per tool (if timing data available)
  - [ ] Most common error messages
- [ ] Add to monitor dashboard (summary view)
- [ ] Create standalone analysis CLI: `python -m lea.analyze [session_id]`
  - [ ] Print detailed statistics to terminal
  - [ ] Optionally export to JSON

**Files to create**:
- `lea/analyze.py` (~150-200 lines)

**Estimated effort**: 3-4 hours

---

### P1: Snapshot System
**Purpose**: Compare before/after state of workspace files

**Tasks**:
- [ ] Create `lea/snapshots.py` module
- [ ] Implement `capture_snapshot_before()`
  - [ ] Copy all .lean files from workspace to `results/{session_id}/snapshots/before/`
  - [ ] Save file metadata: paths, sizes, line counts, sorry counts
  - [ ] Return snapshot manifest JSON
- [ ] Implement `capture_snapshot_after()`
  - [ ] Copy final state to `results/{session_id}/snapshots/after/`
  - [ ] Compare with before snapshot
  - [ ] Generate diff summary: files added, modified, deleted
  - [ ] Calculate metrics: lines changed, sorries added/removed
- [ ] Integrate into `run()` when `result_dir` is provided
  - [ ] Capture before snapshot at start
  - [ ] Capture after snapshot at end
  - [ ] Include diff summary in final_result.json
- [ ] Add `--reset-from-original` option to CLI
  - [ ] Find latest snapshot for a session
  - [ ] Restore files from `before/` directory

**Files to create**:
- `lea/snapshots.py` (~200-250 lines)

**Files to modify**:
- `lea/agent.py` (integrate snapshot calls)
- `lea/cli.py` (add --reset-from-original flag)

**Estimated effort**: 4-5 hours

---

### P2: Enhanced Session Management
**Purpose**: Better tools for exploring and managing session history

**Tasks**:
- [ ] Enhance `list_sessions()` output
  - [ ] Show success/failure status (if available)
  - [ ] Display token usage and estimated cost
  - [ ] Show active files worked on
  - [ ] Add filtering options (by model, by date range, by status)
- [ ] Add session comparison tool
  - [ ] Compare two sessions side-by-side
  - [ ] Show different tool usage patterns
  - [ ] Compare token efficiency
- [ ] Add session cleanup utilities
  - [ ] Archive old sessions
  - [ ] Delete failed sessions
  - [ ] Export sessions to external format

**Files to modify**:
- `lea/agent.py` (enhance list_sessions)

**Files to create**:
- `lea/session_manager.py` (~150 lines)

**Estimated effort**: 3-4 hours

---

## Phase 3: Evaluation & Batch Processing Improvements

### P1: Enhanced Eval Result Tracking
**Purpose**: Better observability for long-running benchmark evaluations

**Tasks**:
- [ ] Modify `eval/run_minif2f.py` to use result_dir infrastructure
  - [ ] Each problem gets its own result directory
  - [ ] Tool timeline and incremental logs available
  - [ ] Can monitor individual problems during eval
- [ ] Add eval-level monitoring dashboard
  - [ ] Show progress across all problems
  - [ ] Display current problem being worked on
  - [ ] Show running pass rate
  - [ ] Estimate time remaining
- [ ] Enhanced per-problem transcripts
  - [ ] Include tool usage stats
  - [ ] Include file snapshots
  - [ ] Track compilation attempts and errors
- [ ] Aggregate statistics across eval run
  - [ ] Tool usage patterns for successful vs failed proofs
  - [ ] Average turns for different problem types
  - [ ] Token usage analysis

**Files to modify**:
- `eval/run_minif2f.py` (~100 lines of changes)
- Similar changes to `eval/run_fqb.py`, `eval/run_baseline.py`

**Files to create**:
- `eval/monitor_eval.py` (~200 lines)
- `eval/analyze_eval.py` (~250 lines)

**Estimated effort**: 5-6 hours

---

### P2: Comparative Analysis Tools
**Purpose**: Compare multiple sessions or eval runs

**Tasks**:
- [ ] Create comparison utilities
  - [ ] Compare tool usage across sessions
  - [ ] Compare token efficiency
  - [ ] Identify successful patterns
- [ ] Generate comparison reports
  - [ ] Side-by-side session comparison
  - [ ] Multi-session aggregate statistics
  - [ ] Export to CSV for external analysis
- [ ] Visualization helpers
  - [ ] Timeline comparison charts (text-based)
  - [ ] Tool usage distribution graphs

**Files to create**:
- `lea/compare.py` (~200-300 lines)

**Estimated effort**: 4-5 hours

---

## Phase 4: Advanced Features & Visualization

### P2: HTML Visualization System
**Purpose**: Post-hoc interactive analysis of sessions

**Tasks**:
- [ ] Create HTML template with embedded JavaScript
  - [ ] Timeline view of all tool calls
  - [ ] Clickable events to see details
  - [ ] Tool usage bar charts
  - [ ] Turn-by-turn navigation
  - [ ] Text diff viewer for file changes
- [ ] Generate self-contained HTML files
  - [ ] Embed all data as JSON
  - [ ] No external dependencies
  - [ ] Works offline
- [ ] Add CLI: `python -m lea.visualize [session_id]`
  - [ ] Generate `results/{session_id}/visualization.html`
  - [ ] Optionally open in browser

**Files to create**:
- `lea/visualize.py` (~400-500 lines including HTML template)

**Estimated effort**: 8-10 hours

---

### P3: Streaming Output Capture
**Purpose**: Real-time text streaming visibility (beyond turn-level)

**Tasks**:
- [ ] Add optional streaming output file
  - [ ] Write text deltas to file as they arrive
  - [ ] Monitor can tail this file for sub-second updates
- [ ] Enhance monitor to show live streaming text
  - [ ] Show partial responses as they're generated
  - [ ] Update more frequently than 2-second session poll
- [ ] Add streaming performance metrics
  - [ ] Time to first token
  - [ ] Tokens per second
  - [ ] Streaming latency

**Files to modify**:
- `lea/agent.py` (add streaming output file)
- `lea/monitor.py` (add streaming text display)

**Estimated effort**: 3-4 hours

---

### P3: Advanced Monitoring Features
**Purpose**: Polish and advanced capabilities

**Tasks**:
- [ ] Add filesystem watching (instead of polling)
  - [ ] Use `watchdog` library to detect file changes
  - [ ] Instant updates when files modified
- [ ] Add alerting/notifications
  - [ ] Desktop notifications when session completes
  - [ ] Slack/Discord webhooks for eval runs
- [ ] Multi-session dashboard
  - [ ] Monitor multiple concurrent sessions
  - [ ] Switch between sessions with keyboard
- [ ] Performance profiling
  - [ ] Track time spent in each tool
  - [ ] Identify bottlenecks

**Files to create/modify**:
- Enhance `lea/monitor.py` (~200 lines additional)

**Estimated effort**: 6-8 hours

---

### P3: Statement Tracking (Adapted)
**Purpose**: Detect if agent changes problem statement from original task

**Tasks**:
- [ ] Extract theorem statement from original task description
- [ ] Parse final .lean file to extract actual theorem written
- [ ] Compare to detect drift
- [ ] Log warning if statements don't match
- [ ] Useful for catching misinterpretations

**Files to create**:
- `lea/statement_tracker.py` (~100-150 lines)

**Note**: Lower priority since Lea writes new files rather than editing existing ones

**Estimated effort**: 3-4 hours

---

## Implementation Roadmap

### Week 1: Core Observability (MVP)
**Goal**: Real-time monitoring of active sessions

- [ ] P0: Real-Time Monitoring Dashboard
- [ ] P0: Incremental Result Logging
- [ ] P1: File Statistics Tracking

**Deliverable**: Can run `python -m lea.monitor` to watch an active session in real-time

**Total effort**: ~10-13 hours

---

### Week 2: Analysis & History
**Goal**: Understand completed sessions and compare runs

- [ ] P1: Tool Usage Statistics
- [ ] P1: Snapshot System
- [ ] P2: Enhanced Session Management

**Deliverable**: Can analyze any session with detailed statistics and compare before/after file states

**Total effort**: ~10-13 hours

---

### Week 3: Evaluation Infrastructure
**Goal**: Better observability for benchmark evaluations

- [ ] P1: Enhanced Eval Result Tracking
- [ ] P2: Comparative Analysis Tools

**Deliverable**: Can monitor long-running eval jobs and compare results across runs

**Total effort**: ~9-11 hours

---

### Week 4: Advanced Features (Optional)
**Goal**: Polish and advanced visualization

- [ ] P2: HTML Visualization System
- [ ] P3: Streaming Output Capture
- [ ] P3: Advanced Monitoring Features

**Deliverable**: Professional HTML reports and enhanced real-time monitoring

**Total effort**: ~17-22 hours

---

## Dependencies & Setup

### New Python Dependencies
```bash
# For monitoring dashboard
pip install rich

# For filesystem watching (optional, P3)
pip install watchdog

# All others use stdlib
```

### Directory Structure
```
lea-prover/
├── lea/
│   ├── monitor.py          # P0: Real-time monitoring
│   ├── analyze.py          # P1: Session analysis
│   ├── snapshots.py        # P1: Before/after snapshots
│   ├── visualize.py        # P2: HTML generation
│   ├── tracking.py         # P1: Shared tracking utilities
│   ├── session_manager.py  # P2: Session management
│   └── statement_tracker.py # P3: Statement comparison
├── eval/
│   ├── monitor_eval.py     # P1: Eval monitoring
│   └── analyze_eval.py     # P1: Eval analysis
└── results/                # Auto-created
    └── {session_id}/
        ├── metadata.json
        ├── tool_timeline.jsonl
        ├── turn_N.json
        ├── final_result.json
        ├── snapshots/
        │   ├── before/
        │   └── after/
        └── visualization.html
```

---

## Testing Strategy

### Unit Tests
- [ ] Test `track_file_stats()` with sample .lean files
- [ ] Test `analyze_session()` with mock session data
- [ ] Test snapshot capture and restore
- [ ] Test tool usage parsing

### Integration Tests
- [ ] Run monitor on a real session (manual)
- [ ] Run full eval with monitoring (manual)
- [ ] Test session resume with snapshots
- [ ] Test concurrent session monitoring

### Validation
- [ ] Monitor a known long-running session
- [ ] Compare statistics with manual inspection
- [ ] Verify snapshot restore functionality
- [ ] Test on multiple models (Gemini, Claude, OpenAI)

---

## Success Metrics

### Week 1 (Core Observability)
- ✅ Can monitor any active session in real-time
- ✅ See tool calls within 2 seconds of execution
- ✅ Track file line counts and sorry counts live
- ✅ Know immediately if agent is stuck or making progress

### Week 2 (Analysis)
- ✅ Generate detailed statistics for any session
- ✅ Compare before/after file states
- ✅ Identify tool usage patterns
- ✅ Understand why sessions succeed or fail

### Week 3 (Evaluation)
- ✅ Monitor long-running eval jobs
- ✅ Track per-problem progress during evals
- ✅ Compare eval runs to identify improvements
- ✅ Aggregate statistics across benchmark runs

### Week 4 (Polish)
- ✅ Beautiful HTML reports for sharing
- ✅ Sub-second streaming text visibility
- ✅ Professional monitoring experience

---

## Design Principles (Adapted from Numina)

1. **Immediate writes** - Save data as it happens, not at the end
2. **Minimal invasiveness** - No major refactoring of core agent loop
3. **Structured storage** - JSON files in predictable locations
4. **Self-contained tools** - Monitor runs separately from agent
5. **Graceful degradation** - Monitoring is optional, agent works without it
6. **Backwards compatible** - Existing sessions still readable

---

## Migration Notes

### Existing Sessions
- Old session files in `~/.lea/sessions/` remain compatible
- New fields are optional - analysis tools handle missing data gracefully
- Can add `result_dir` tracking to existing sessions retroactively (read-only analysis)

### Eval Results
- Existing eval result JSONs remain valid
- New transcript format is superset of old format
- Migration script not needed - tools detect format version

---

## Open Questions

1. **Monitoring frequency**: 2-second poll vs sub-second streaming?
   - **Decision**: Start with 2s, add streaming in P3 if needed

2. **Result directory location**: Separate from `~/.lea/sessions/`?
   - **Proposal**: `results/{session_id}/` for detailed tracking, sessions dir for lightweight logs

3. **Snapshot storage**: Include in results dir or separate?
   - **Decision**: Include in results dir for co-location

4. **Tool timeline format**: JSONL vs JSON array?
   - **Decision**: JSONL for easy appending and streaming

5. **Monitor UI framework**: `rich` vs custom?
   - **Decision**: `rich` for consistency with numina and better output

---

## Future Enhancements (Beyond P3)

- Web-based dashboard (replace terminal UI)
- Database storage for large-scale analysis
- Distributed monitoring for parallel eval runs
- Integration with experiment tracking (Weights & Biases, MLflow)
- Automated performance regression detection
- Proof structure visualization (dependency graphs)
- LLM cost optimization recommendations based on tool patterns

---

## Notes

- This plan prioritizes **real-time observability** (your stated need) as P0
- Focuses on **minimal changes** to core agent logic
- Leverages existing session storage format where possible
- Can implement incrementally - each phase delivers value independently
- Estimated total effort: ~40-60 hours for all phases

---

**Document Version**: 1.0
**Created**: 2026-04-23
**Author**: Implementation plan for Lea agent observability enhancements
