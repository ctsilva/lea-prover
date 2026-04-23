# Lessons Learned - Lea Agent Best Practices

This file contains patterns, common mistakes, and best practices learned from running the Lea agent on real problems. These guidelines are automatically included in the system prompt.

**Note**: This file will be updated as we discover patterns from benchmark evaluations and complex proof attempts.

## Performance Patterns

### Import Strategy
- For very simple proofs (basic arithmetic, trivial equalities), try standard library tactics first: `rfl`, `decide`, `simp`
- Only add `import Mathlib` or `import Mathlib.Tactic` if stdlib tactics fail
- Mathlib imports add compilation overhead - use them when you need their power, not by default

## Common Proof Strategies

_(To be populated based on successful proof patterns)_

## Pitfalls to Avoid

_(To be populated based on failed attempts and error analysis)_

---

**How to use this file:**
1. Run eval benchmarks with monitoring enabled (`--result-dir`)
2. Analyze patterns from successful vs failed proofs
3. Add discovered patterns here
4. The agent will automatically learn from these lessons in future runs
