# LEA Evaluation Analysis Summary

## Test Run Results

**Overall Performance**: 71.4% success rate (10/14 problems solved)

### Key Findings

#### 1. Turn Count is a Strong Predictor
- ✅ **All problems solved in ≤18 turns succeeded (100%)**
- ❌ **All problems reaching 20 turns failed (0%)**
- 💡 This suggests the max_turns=20 is working as intended as a cutoff
- Average turns: 12.8 (pass) vs 20.0 (fail)

#### 2. Token Efficiency
- Total tokens used: **2.28M tokens**
  - Input: 2.19M tokens (95.7%)
  - Output: 99K tokens (4.3%)
- Average per problem: **163K tokens**
- Failed problems use **1.2x more tokens** on average
  - Pass: 154K tokens
  - Fail: 186K tokens

#### 3. Tool Usage Patterns
Most frequently used tools:
1. **lean_check** (70 calls, avg 57.7s) - Verification is the bottleneck
2. **write_file** (64 calls, avg 2ms) - Lots of iteration
3. **search_mathlib** (31 calls, avg 1.7s) - Looking for existing theorems
4. **edit_file** (18 calls) - Some refinement
5. **bash** (12 calls, avg 42.9s) - Mostly for testing

#### 4. Success Patterns

**Quick Solvers** (≤10 turns, 3 problems):
- aime_1984_p15: 5 turns, 24K tokens
- aime_1983_p9: 7 turns, 26K tokens
- aimeII_2001_p3 (session 2): 9 turns, 78K tokens
- Average: **42.6K tokens** - very efficient!

**Iterative Solvers** (>10 turns, 7 problems):
- aime_1984_p5: 15 turns, 331K tokens (most expensive success)
- aimeII_2001_p3 (session 1): 17 turns, 330K tokens
- Average: **201.5K tokens** - 4.7x more expensive

**Failed at Limit** (all 4 failures hit 20 turn limit):
- aimeI_2000_p7: 193K tokens
- aime_1987_p8: 289K tokens (most expensive overall)
- aime_1988_p4: 105K tokens
- aime_1990_p2: 159K tokens

#### 5. Problem-Specific Insights

**aimeII_2001_p3** (3 attempts, 100% success):
- Best: 9 turns, 78K tokens
- Worst: 17 turns, 330K tokens
- This problem has high variance - some strategies are 4x more efficient!

**aimeII_2020_p6** (3 attempts, 100% success):
- Best: 13 turns, 84K tokens
- Worst: 18 turns, 167K tokens
- More consistent solving approach

## Recommendations

### 1. Optimize Early Strategy
The 3 problems solved in ≤10 turns used **4.7x fewer tokens**. Consider:
- More aggressive upfront search_mathlib usage
- Better initial problem decomposition
- Earlier pattern recognition

### 2. lean_check Optimization
`lean_check` averages **57.7 seconds** - this is the main bottleneck:
- 70 calls × 57.7s = **4,039 seconds** (67 minutes) of compilation time
- Could benefit from:
  - Incremental compilation
  - Caching of common imports
  - Parallel checking if running multiple problems

### 3. 20-Turn Limit Analysis
All 4 failures hit the 20-turn limit. Two possibilities:
- **Good**: The limit prevents runaway sessions
- **Bad**: Some problems might be solvable with 21-25 turns

Recommendation: Test with `max_turns=25` on failed problems to see if they're close.

### 4. Cost Analysis
At current token usage:
- **Per problem**: ~163K tokens average
- **Successful solve**: ~154K tokens
- **Failed attempt**: ~186K tokens

If running GPT-4 class models:
- Input: ~$22/problem (at $0.01/1K tokens)
- Output: ~$0.20/problem (at $0.02/1K tokens)
- **Total: ~$22.20/problem** at 71% success rate

### 5. Strategies to Improve

**For Quick Wins** (target: more sub-10 turn solves):
- Improve initial problem analysis
- Better theorem search in first few turns
- Template-based approaches for common patterns

**For Borderline Cases** (15-19 turns):
- Add reflection/backtracking when stuck
- Simplification strategies before giving up
- Alternative proof approaches

**For Hard Problems** (hitting 20 turn limit):
- Early detection of impossibility
- Request human intervention signal
- Save partial progress for later analysis

## Visualization Tools Created

### 1. Session Visualizer
```bash
python eval/visualize_session.py <session_dir> <output.html>
```
- Interactive timeline of all tool calls
- Click to see full details
- Tool usage statistics
- Self-contained HTML

### 2. Batch Visualizer
```bash
python eval/visualize_all_sessions.py <eval_results_dir> <output_dir>
```
- Generates visualizations for all sessions
- Creates index.html for easy browsing
- Groups by problem

### 3. Results Analyzer
```bash
python eval/analyze_results.py <eval_results_dir>
```
- Comprehensive statistics
- Tool usage analysis
- Success patterns
- Token efficiency metrics

### 4. Session Comparator
```bash
python eval/compare_sessions.py <problem_name> <eval_results_dir>
```
- Compare multiple attempts at same problem
- Find best/worst strategies
- Identify variance in approaches

## Next Steps

1. **Run More Problems**: Expand to 50-100 problems for better statistics
2. **A/B Testing**: Test different prompts/strategies on same problems
3. **Cost Optimization**: Focus on getting more problems into the "quick solver" category
4. **Failure Analysis**: Deep dive into the 4 failed problems using visualizations
5. **Benchmark Comparison**: Compare against other Lean theorem provers

## Files Created

- `eval/visualize_session.py` - Single session HTML generator
- `eval/visualize_all_sessions.py` - Batch visualization with index
- `eval/analyze_results.py` - Statistical analysis
- `eval/compare_sessions.py` - Problem-specific comparison
- `eval/VISUALIZATION_README.md` - Documentation
- `eval/ANALYSIS_SUMMARY.md` - This file

All visualizations are in: `visualizations/index.html`
