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

### P0: Real-Time Monitoring Dashboard ✅ IMPLEMENTED
**Purpose**: See what the agent is doing right now without waiting for completion

**Tasks**:
- [x] Create `lea/monitor.py` with basic dashboard
  - [x] Auto-detect latest session or accept session ID
  - [x] Poll session JSON file every 2 seconds (configurable)
  - [x] Display current turn number and elapsed time
  - [x] Show tool call counts (read_file, write_file, lean_check, etc.)
  - [x] Display last 6 tool calls with args
  - [x] Show last assistant text output (truncated to 400 chars)
  - [x] Auto-exit when session completes
- [x] Use `rich` library for formatted terminal output
  - [x] Header: session ID, model, status, duration
  - [x] Status panel (left): turns, tokens, active files with line/sorry counts
  - [x] Tool stats panel (right top): tool names, call counts, error counts
  - [x] Recent activity panel (right bottom): last N tool calls
  - [x] Text preview panel (bottom): latest agent output
- [x] Add CLI entry point: `python -m lea.monitor [session_id]`
- [x] Handle edge cases:
  - [x] Session file doesn't exist yet
  - [x] Session file is being written (partial JSON) - safe loading
  - [x] Session ID prefix matching

**Files created**:
- `lea/monitor.py` (399 lines - fully featured dashboard)

**Dependencies**:
- `rich` ✅ already in dependencies

**Status**: ✅ Fully implemented and working
**Usage**: `python -m lea.monitor` or `python -m lea.monitor SESSION_ID`

---

### P0: Incremental Result Logging ✅ IMPLEMENTED
**Purpose**: Write progress data immediately so monitoring can work during long turns

**Tasks**:
- [x] Add `result_dir` parameter to `run()` function (optional)
- [x] Create result directory structure: `results/{session_id}/`
- [x] Log tool calls immediately to `tool_timeline.jsonl`
  - [x] One JSON line per tool execution
  - [x] Fields: `timestamp`, `turn`, `tool`, `args`, `result_preview`, `duration_ms`
- [x] Save turn summaries to `turn_N.json` after each turn
  - [x] Tool calls made (with args and result previews)
  - [x] Text output (truncated to 1000 chars)
  - [x] Timestamp and duration
- [x] Save session metadata to `metadata.json` at start
  - [x] Task description
  - [x] Model name
  - [x] Start timestamp
  - [x] Configuration (max_turns, prompt_variant, provider)
- [x] Update final result summary at end: `final_result.json`
  - [x] Success/failure
  - [x] Total turns
  - [x] Total tokens (input + output)
  - [x] Completion timestamp
  - [x] Error message (if failed)

**Files created**:
- `lea/tracking.py` (204 lines - ResultTracker class + helpers)

**Files modified**:
- `lea/agent.py` (integrated ResultTracker throughout)

**Status**: ✅ Fully implemented and working
**Used in**: eval runs already use this infrastructure

---

### P1: File Statistics Tracking ✅ IMPLEMENTED
**Purpose**: Monitor proof progress (line counts, sorry counts)

**Tasks**:
- [x] Create `track_file_stats()` function
  - [x] Count total lines in .lean file
  - [x] Count `sorry` occurrences (regex: `\bsorry\b`)
  - [x] Return `{"lines": int, "sorries": int, "path": str}`
- [x] Integrate into monitoring dashboard
  - [x] Show current stats for files being worked on (up to 3 files)
  - [x] Display in status panel with lines and sorry counts
  - [ ] Color-code based on delta (needs before snapshot comparison)
- [x] Track which files are being actively modified
  - [x] `extract_active_files()` function parses tool calls
  - [x] Identifies .lean files from 'path' arguments
  - [x] Maintains list of active files per session
- [x] File stats function also in tracking.py
  - [x] Same implementation in both places
  - [x] Used for snapshot manifests

**Files modified**:
- `lea/monitor.py` (includes `track_file_stats()` and `extract_active_files()`)
- `lea/tracking.py` (includes `track_file_stats()` and `extract_files_from_args()`)

**Status**: ✅ Core functionality implemented
**Note**: Color-coding based on deltas would require comparing to initial snapshot

---

## Phase 2: Enhanced Analysis & Debugging

### P1: Tool Usage Statistics ✅ IMPLEMENTED
**Purpose**: Understand patterns in how agent uses tools

**Tasks**:
- [x] Create `analyze_session()` function
  - [x] Parse session messages to extract all tool calls
  - [x] Count by tool name
  - [x] Detect errors (tool results starting with "Error:")
  - [x] Calculate success rates per tool
  - [x] Track temporal patterns (tools by turn, common sequences)
- [x] Generate statistics report
  - [x] Total calls by tool type
  - [x] Success vs error rates
  - [x] Tool usage sequences
  - [x] Common error patterns
  - [x] Per-turn error tracking
- [x] Create standalone analysis CLI: `python -m lea.analyze [session_id]`
  - [x] Print detailed statistics to terminal (using Rich)
  - [x] Export to JSON with `--export FILE`
  - [x] Beautiful formatted tables for all stats
- [ ] Add to monitor dashboard (deferred - monitor already shows basic stats)

**Files created**:
- `lea/analyze.py` (295 lines with comprehensive analysis)

**Output includes**:
- Summary statistics (turns, tokens, error rate)
- Tool usage table (calls, success, errors, success rate)
- Common tool sequences (pattern detection)
- Error analysis (common patterns, recent errors)

**Status**: ✅ Fully implemented and tested
**Usage**: `python -m lea.analyze` or `python -m lea.analyze SESSION_ID --export stats.json`

---

### P1: Snapshot System & Intermediate File Tracking ✅ IMPLEMENTED
**Purpose**: Compare before/after state of workspace files AND track evolution of files across turns

**Tasks**:
- [x] Create `lea/snapshots.py` module
- [x] Implement `capture_snapshot_before()`
  - [x] Copy all .lean files from workspace to `results/{session_id}/snapshots/before/`
  - [x] Save file metadata: paths, sizes, line counts, sorry counts
  - [x] Return snapshot manifest JSON
- [x] Implement `capture_snapshot_after()`
  - [x] Copy final state to `results/{session_id}/snapshots/after/`
  - [x] Compare with before snapshot
  - [x] Generate diff summary: files added, modified, deleted
  - [x] Calculate metrics: lines changed, sorries added/removed
- [x] **Implement intermediate file snapshots on every modification**
  - [x] After each `write_file` or `edit_file` tool call on `.lean` files, save a copy
  - [x] Save to `results/{session_id}/snapshots/turn_{N}/` with original filename
  - [x] This preserves the complete evolution of the proof across all turns
  - [x] Benefits:
    - See exactly what was checked at each turn (useful for debugging)
    - Reproduce any intermediate state
    - Benchmark performance improvements on actual intermediate files
    - Analyze proof evolution and strategy patterns
- [x] Integrate into `run()` when `result_dir` is provided
  - [x] Capture before snapshot at start
  - [x] Capture intermediate snapshot after each file modification
  - [x] Capture after snapshot at end (on success or max turns)
  - [x] Generate and save diff summary
- [x] Add `restore_from_snapshot()` method to SnapshotManager
  - [x] Can restore from "before", "after", or "turn_N"
  - [x] Preserves directory structure
- [ ] Add `--reset-from-original` option to CLI (deferred - needs CLI work)

**Files created**:
- `lea/snapshots.py` (313 lines with full snapshot tracking)

**Files modified**:
- `lea/agent.py` (integrated snapshot capture at start, per-turn, and end)
- `lea/tracking.py` (added snapshot manager integration and helper methods)

**Status**: ✅ Core implementation complete, tested manually
**Note**: Full end-to-end testing blocked by slow lean_check times (LSP issue)

---

### P2: Enhanced Session Management ✅ IMPLEMENTED
**Purpose**: Better tools for exploring and managing session history

**Tasks**:
- [x] Enhanced session listing
  - [x] Show success/failure status (intelligent detection)
  - [x] Display token usage and estimated cost
  - [x] Show active files worked on
  - [x] Add filtering options (by model, by status)
  - [x] Limit control
- [x] Add session comparison tool
  - [x] Compare two sessions side-by-side
  - [x] Show different tool usage patterns
  - [x] Compare token efficiency
  - [x] Show turn and cost differences
- [x] Add session cleanup utilities
  - [x] Delete failed sessions (with dry-run mode)
  - [x] Confirmation flag for safety
  - [x] Report what would be deleted

**Files created**:
- `lea/session_manager.py` (344 lines - complete session management CLI)

**Files modified**:
- None! (kept agent.py unchanged for backward compatibility)

**Features**:
- **List**: Enhanced session listing with status, tokens, cost
- **Compare**: Side-by-side comparison of two sessions
- **Cleanup**: Safe deletion with dry-run mode

**Status**: ✅ Fully implemented and tested
**Usage**:
```bash
python -m lea.session_manager list --model gpt-5.4
python -m lea.session_manager compare SESSION1 SESSION2
python -m lea.session_manager cleanup --failed --confirm
```

---

## Phase 3: Evaluation & Batch Processing Improvements

### P1: Enhanced Eval Result Tracking ✅ IMPLEMENTED
**Purpose**: Better observability for long-running benchmark evaluations

**Tasks**:
- [x] Eval scripts already use result_dir infrastructure
  - [x] Each problem gets its own result directory (`result_dir/problem_name/`)
  - [x] Tool timeline and incremental logs available (via ResultTracker)
  - [x] Can monitor individual problems during eval
- [x] Add eval-level monitoring dashboard
  - [x] Show progress across all problems
  - [x] Display recent problems with results
  - [x] Show running pass rate
  - [x] Time and turn statistics
- [x] Comprehensive eval analysis tool
  - [x] Summary statistics (pass rate, total problems)
  - [x] Time statistics (avg, min, max for passed/failed)
  - [x] Turn statistics (avg for passed vs failed)
  - [x] Token usage analysis
  - [x] Hardest problems (most turns, failed)
  - [x] Quickest successes
  - [x] Comparison mode for two evals
- [x] Per-problem transcripts already enhanced
  - [x] Include turns and usage stats
  - [x] Full message history
  - [x] Verification output

**Files created**:
- `eval/monitor_eval.py` (234 lines - live eval monitoring dashboard)
- `eval/analyze_eval.py` (369 lines - comprehensive eval analysis with comparison)

**Files modified**:
- None! Eval scripts already had result_dir support

**Status**: ✅ Fully implemented and tested
**Usage**:
```bash
python -m eval.monitor_eval --latest              # Monitor running eval
python -m eval.analyze_eval --latest              # Analyze completed eval
python -m eval.analyze_eval --compare FILE1 FILE2 # Compare two evals
```

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

### P2: HTML Visualization System ✅ COMPLETED
**Purpose**: Post-hoc interactive analysis of sessions

**Tasks**:
- [x] Create HTML template with embedded JavaScript
  - [x] Timeline view of all tool calls
  - [x] Clickable events to see details
  - [x] Tool usage bar charts
  - [x] Turn-by-turn navigation
  - [ ] Text diff viewer for file changes (TODO: enhance with side-by-side diff)
- [x] Generate self-contained HTML files
  - [x] Embed all data as JSON
  - [x] No external dependencies
  - [x] Works offline
- [x] Add CLI scripts
  - [x] `eval/visualize_session.py [session_dir] [output.html]`
  - [x] `eval/visualize_all_sessions.py [eval_results_dir] [output_dir]`
  - [x] Generates index.html for all sessions

**Files created**:
- `eval/visualize_session.py` (~550 lines including HTML template)
- `eval/visualize_all_sessions.py` (~150 lines)

**Usage**:
```bash
# Visualize single session
python eval/visualize_session.py eval_results/test_run/aimeII_2001_p3/20260424-015729/ output.html

# Visualize all sessions and create index
python eval/visualize_all_sessions.py eval_results/test_run/ visualizations/

# Open the index in browser
open visualizations/index.html
```

**Features**:
- Interactive timeline with color-coded turns
- Click any tool call to see full details (args, result, duration)
- Click any turn to see summary of all tool calls in that turn
- Tool usage statistics table with counts and durations
- Session metadata and success/failure status
- Fully self-contained HTML (no external dependencies)
- Works offline

**Actual effort**: ~2 hours

**Recent improvements** (2026-04-24):
- Fixed turn sorting bug (numerical vs alphabetical)
- Replaced modal popup with inline details panel
- Added 3-column layout with sticky details
- Visual selection highlighting
- All 14 test sessions regenerated

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
