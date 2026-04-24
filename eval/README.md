# LEA Evaluation & Analysis Tools

Complete toolkit for analyzing LEA agent performance on mathematical theorem proving.

## Quick Start

### 1. Visualize Your Results

```bash
# Visualize all sessions and create an index
python eval/visualize_all_sessions.py eval_results/test_run/ visualizations/

# Open the index in your browser
open visualizations/index.html
```

### 2. Analyze Performance

```bash
# Get comprehensive statistics
python eval/analyze_results.py eval_results/test_run/
```

### 3. Compare Strategies

```bash
# Compare multiple attempts at the same problem
python eval/compare_sessions.py aimeII_2001_p3 eval_results/test_run/
```

## What You Get

### 📊 Statistical Analysis
- Success rate breakdown
- Turn count patterns
- Token usage analysis
- Tool efficiency metrics
- Success predictors

### 🎨 Interactive Visualizations
- Timeline of all tool calls
- Clickable details for each call
- Tool usage bar charts
- Turn-by-turn navigation
- Session comparisons

### 💡 Actionable Insights
- Which problems are solvable quickly?
- Where do failures occur?
- What tools are bottlenecks?
- How much variance across attempts?
- Cost per problem analysis

## Tools Overview

### 1. `visualize_session.py`
Generate an interactive HTML visualization for a single session.

**Usage**:
```bash
python eval/visualize_session.py <session_dir> [output.html]
```

**Example**:
```bash
python eval/visualize_session.py \
  eval_results/test_run/aimeII_2001_p3/20260424-015729/ \
  session.html
```

**Features**:
- Color-coded timeline by turn
- Click any tool call to see args/results
- Tool usage statistics
- Session metadata
- 100% offline, self-contained HTML

---

### 2. `visualize_all_sessions.py`
Batch generate visualizations for all sessions.

**Usage**:
```bash
python eval/visualize_all_sessions.py <eval_results_dir> [output_dir]
```

**Example**:
```bash
python eval/visualize_all_sessions.py eval_results/test_run/ visualizations/
```

**Output**:
- One HTML file per session
- `index.html` listing all sessions
- Grouped by problem
- Click-through navigation

---

### 3. `analyze_results.py`
Comprehensive statistical analysis.

**Usage**:
```bash
python eval/analyze_results.py <eval_results_dir>
```

**Example**:
```bash
python eval/analyze_results.py eval_results/test_run/
```

**Provides**:
- Overall success rate
- Turn statistics (avg, min, max)
- Token usage breakdown
- Top tool usage
- Slowest tools
- Success patterns
- Problem breakdown
- Key insights

**Output**:
- Formatted console output
- `analysis.json` with detailed data

---

### 4. `compare_sessions.py`
Compare multiple attempts at the same problem.

**Usage**:
```bash
python eval/compare_sessions.py <problem_name> <eval_results_dir>
```

**Example**:
```bash
python eval/compare_sessions.py aimeII_2001_p3 eval_results/test_run/
```

**Shows**:
- All sessions for the problem
- Success/failure status
- Turn counts
- Token usage
- Best solution
- Average performance

---

## Your Current Results

Based on your test run:

| Metric | Value |
|--------|-------|
| **Success Rate** | 71.4% (10/14 problems) |
| **Avg Turns (pass)** | 12.8 turns |
| **Avg Turns (fail)** | 20.0 turns |
| **Avg Tokens** | 163K tokens/problem |
| **Total Tokens** | 2.28M tokens |

### Key Findings

1. **All failures hit the 20-turn limit** - Consider testing with max_turns=25
2. **Quick solvers (≤10 turns) use 4.7x fewer tokens** - Optimize early strategy
3. **lean_check is the bottleneck** - 57.7s average, 67 minutes total
4. **High variance on same problems** - Some strategies 4x more efficient

See [`ANALYSIS_SUMMARY.md`](ANALYSIS_SUMMARY.md) for detailed insights.

## Workflow

### After Running Evaluations

1. **Quick overview**:
   ```bash
   python eval/analyze_results.py eval_results/test_run/
   ```

2. **Visual exploration**:
   ```bash
   python eval/visualize_all_sessions.py eval_results/test_run/ viz/
   open viz/index.html
   ```

3. **Deep dive on interesting problems**:
   ```bash
   # Find problems with multiple attempts
   python eval/compare_sessions.py aimeII_2001_p3 eval_results/test_run/

   # Open the visualization
   open viz/aimeII_2001_p3_20260424-010312.html  # Best solution
   ```

4. **Identify patterns**:
   - Look at successful quick solves (≤10 turns)
   - Examine borderline cases (15-19 turns)
   - Investigate failures at limit (20 turns)

### Comparing Strategies

To A/B test different approaches:

1. Run evaluations with strategy A → `eval_results/strategy_a/`
2. Run evaluations with strategy B → `eval_results/strategy_b/`
3. Compare:
   ```bash
   python eval/analyze_results.py eval_results/strategy_a/
   python eval/analyze_results.py eval_results/strategy_b/
   ```

## File Structure

```
eval/
├── README.md                      # This file
├── VISUALIZATION_README.md        # Detailed viz docs
├── ANALYSIS_SUMMARY.md           # Your test run insights
├── visualize_session.py          # Single session viz
├── visualize_all_sessions.py     # Batch viz + index
├── analyze_results.py            # Statistical analysis
└── compare_sessions.py           # Problem comparison

eval_results/
└── test_run/
    ├── analysis.json             # Generated statistics
    ├── aimeII_2001_p3/
    │   ├── 20260423-213317/
    │   │   ├── metadata.json
    │   │   ├── final_result.json
    │   │   ├── tool_timeline.jsonl
    │   │   └── turn_*.json
    │   └── 20260424-015729/
    │       └── ...
    └── ...

visualizations/
├── index.html                    # Main index
├── aimeII_2001_p3_20260423-213317.html
├── aimeII_2001_p3_20260424-015729.html
└── ...
```

## Tips & Tricks

### Finding Interesting Sessions

**Most efficient success**:
```bash
# Look for low turn count + low tokens in analysis output
python eval/analyze_results.py eval_results/test_run/ | grep "PASS.*[0-9] turns"
```

**Borderline failures**:
```bash
# Check which problems almost succeeded
python eval/analyze_results.py eval_results/test_run/ | grep "20 turns"
```

**High variance problems**:
```bash
# Compare sessions with same problem name
for prob in aimeII_2001_p3 aimeII_2020_p6; do
  python eval/compare_sessions.py $prob eval_results/test_run/
done
```

### Visualizing Specific Patterns

**Tool usage over time**:
Open a visualization and look at the timeline - you can spot:
- Cycles of write_file → lean_check
- Bursts of search_mathlib when stuck
- Long gaps = slow lean_check

**Error patterns**:
Click on failed sessions and examine:
- Which turn did errors start?
- What was tried before failure?
- Were there repeated similar errors?

### Performance Optimization

Based on analysis, focus on:

1. **Early wins** - Problems solved in <10 turns
   - Study what made them quick
   - Apply patterns to other problems

2. **Tool bottlenecks** - lean_check at 57.7s avg
   - Consider caching
   - Parallel execution
   - Incremental compilation

3. **Token efficiency** - 4.7x difference between quick vs slow
   - Reduce verbose searching
   - More focused edits
   - Better initial strategies

## Integration with Other Tools

### With browse_results.py
```bash
# Interactive browsing → find interesting session → visualize it
python eval/browse_results.py eval_results/test_run/
# Note the session path, then:
python eval/visualize_session.py <noted_path> interesting.html
```

### With monitor_eval.py
```bash
# Monitor running eval, then analyze when done
python eval/monitor_eval.py eval_results/new_run/
# Wait for completion...
python eval/analyze_results.py eval_results/new_run/
```

## Troubleshooting

**No sessions found**:
- Check directory path
- Ensure `metadata.json` and `final_result.json` exist

**Visualization not loading**:
- Open via `file://` protocol
- Check browser console for errors
- Ensure JavaScript is enabled

**Analysis shows 0 problems**:
- Verify session structure matches expected format
- Check JSON files are valid

## Future Enhancements

Potential additions:
- [ ] Aggregate comparison across multiple runs
- [ ] Export to CSV for spreadsheet analysis
- [ ] Diff viewer for file changes
- [ ] Cost calculator with configurable rates
- [ ] Success predictor based on early turns
- [ ] Automated report generation
- [ ] Integration with CI/CD

## Contributing

To add new analysis features:

1. Study the data structure in `tool_timeline.jsonl` and turn JSONs
2. Add your analysis to `analyze_results.py` or create new script
3. Test on existing eval results
4. Update this README

## Questions?

See also:
- [`VISUALIZATION_README.md`](VISUALIZATION_README.md) - Detailed visualization docs
- [`ANALYSIS_SUMMARY.md`](ANALYSIS_SUMMARY.md) - Your test run insights
- [`../OBSERVABILITY_PLAN.md`](../OBSERVABILITY_PLAN.md) - Overall observability strategy
