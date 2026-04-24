#!/usr/bin/env python3
"""
Generate interactive HTML visualizations for LEA agent sessions.

Usage:
    python visualize_session.py <session_dir> [output.html]

Example:
    python visualize_session.py eval_results/test_run/aimeII_2001_p3/20260424-015729/ session.html
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import difflib

def load_session_data(session_dir: Path) -> Dict[str, Any]:
    """Load all session data from directory."""
    data = {
        "metadata": {},
        "turns": [],
        "timeline": [],
        "final_result": {},
        "snapshots": []
    }

    # Load metadata
    metadata_file = session_dir / "metadata.json"
    if metadata_file.exists():
        with open(metadata_file) as f:
            data["metadata"] = json.load(f)

    # Load final result
    final_result_file = session_dir / "final_result.json"
    if final_result_file.exists():
        with open(final_result_file) as f:
            data["final_result"] = json.load(f)

    # Load timeline
    timeline_file = session_dir / "tool_timeline.jsonl"
    if timeline_file.exists():
        with open(timeline_file) as f:
            data["timeline"] = [json.loads(line) for line in f]

    # Load turn data
    turn_files = sorted(session_dir.glob("turn_*.json"))
    for turn_file in turn_files:
        with open(turn_file) as f:
            data["turns"].append(json.load(f))

    return data

def compute_tool_stats(timeline: List[Dict]) -> Dict[str, Any]:
    """Compute statistics about tool usage."""
    tool_counts = {}
    tool_durations = {}

    for entry in timeline:
        tool = entry.get("tool", "unknown")
        duration = entry.get("duration_ms", 0)

        tool_counts[tool] = tool_counts.get(tool, 0) + 1
        if tool not in tool_durations:
            tool_durations[tool] = []
        tool_durations[tool].append(duration)

    stats = {
        "counts": tool_counts,
        "total_calls": sum(tool_counts.values()),
        "avg_durations": {
            tool: sum(durs) / len(durs) if durs else 0
            for tool, durs in tool_durations.items()
        },
        "total_durations": {
            tool: sum(durs) for tool, durs in tool_durations.items()
        }
    }

    return stats

def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;"))

def truncate_text(text: str, max_len: int = 100) -> str:
    """Truncate text to max length."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."

def format_duration(ms: float) -> str:
    """Format duration in milliseconds to readable string."""
    if ms < 1000:
        return f"{ms:.0f}ms"
    elif ms < 60000:
        return f"{ms/1000:.1f}s"
    else:
        return f"{ms/60000:.1f}min"

def generate_html(data: Dict[str, Any], session_dir: Path) -> str:
    """Generate HTML visualization."""
    metadata = data["metadata"]
    turns = data["turns"]
    timeline = data["timeline"]
    final_result = data["final_result"]
    stats = compute_tool_stats(timeline)

    # Extract session info
    session_id = metadata.get("session_id", session_dir.name)
    task = metadata.get("task", "No task description")
    model = metadata.get("model", "unknown")
    started_at = metadata.get("started_at", "")

    completed_at = final_result.get("completed_at", "")
    success = final_result.get("success", False)
    error = final_result.get("error")
    total_turns = final_result.get("turns", len(turns))
    usage = final_result.get("usage", {})

    # Build timeline HTML
    timeline_html = []
    for i, entry in enumerate(timeline):
        tool = entry.get("tool", "unknown")
        turn = entry.get("turn", 0)
        timestamp = entry.get("timestamp", "")
        duration = entry.get("duration_ms", 0)
        result_preview = entry.get("result_preview", "")
        args = entry.get("args", {})

        timeline_html.append(f'''
        <div class="timeline-entry" onclick="showToolDetails({i})">
            <div class="timeline-marker turn-{turn}"></div>
            <div class="timeline-content">
                <div class="timeline-header">
                    <span class="tool-name">{escape_html(tool)}</span>
                    <span class="turn-badge">Turn {turn}</span>
                    <span class="duration">{format_duration(duration)}</span>
                </div>
                <div class="timeline-preview">{escape_html(truncate_text(result_preview, 80))}</div>
            </div>
        </div>
        ''')

    # Build turn summaries - sort by turn number
    turn_summaries = []
    sorted_turns = sorted(turns, key=lambda t: t.get("turn", 0))
    for turn in sorted_turns:
        turn_num = turn.get("turn", 0)
        turn_duration = turn.get("duration_s", 0)
        tool_calls = turn.get("tool_calls", [])
        num_tools = len(tool_calls)

        turn_summaries.append(f'''
        <div class="turn-card" onclick="showTurnDetails({turn_num - 1})">
            <div class="turn-header">
                <h3>Turn {turn_num}</h3>
                <span class="turn-meta">{num_tools} tool calls • {turn_duration:.1f}s</span>
            </div>
            <div class="turn-tools">
                {", ".join([t.get("tool", "?") for t in tool_calls[:5]])}
                {"..." if num_tools > 5 else ""}
            </div>
        </div>
        ''')

    # Build tool stats chart data
    tool_chart_data = []
    for tool, count in sorted(stats["counts"].items(), key=lambda x: -x[1]):
        avg_dur = stats["avg_durations"].get(tool, 0)
        total_dur = stats["total_durations"].get(tool, 0)
        tool_chart_data.append({
            "tool": tool,
            "count": count,
            "avg_duration": avg_dur,
            "total_duration": total_dur
        })

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Session Visualization - {session_id}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}
        header {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{ margin-bottom: 10px; color: #1a1a1a; }}
        .session-meta {{
            color: #666;
            font-size: 14px;
            margin-top: 10px;
        }}
        .status-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
            margin-left: 10px;
        }}
        .status-success {{ background: #d4edda; color: #155724; }}
        .status-failure {{ background: #f8d7da; color: #721c24; }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr 2fr 1.5fr;
            gap: 20px;
            margin-bottom: 20px;
        }}
        .panel {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .panel h2 {{
            margin-bottom: 15px;
            font-size: 18px;
            color: #1a1a1a;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-bottom: 20px;
        }}
        .stat-card {{
            padding: 15px;
            background: #f8f9fa;
            border-radius: 6px;
        }}
        .stat-label {{
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: 700;
            color: #1a1a1a;
            margin-top: 5px;
        }}
        .timeline {{
            max-height: 600px;
            overflow-y: auto;
        }}
        .timeline-entry {{
            display: flex;
            gap: 15px;
            margin-bottom: 15px;
            cursor: pointer;
            transition: all 0.2s;
            padding: 10px;
            border-radius: 6px;
        }}
        .timeline-entry:hover {{
            background: #f8f9fa;
        }}
        .timeline-marker {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-top: 6px;
            flex-shrink: 0;
        }}
        .timeline-marker.turn-1 {{ background: #007bff; }}
        .timeline-marker.turn-2 {{ background: #28a745; }}
        .timeline-marker.turn-3 {{ background: #ffc107; }}
        .timeline-marker.turn-4 {{ background: #dc3545; }}
        .timeline-marker.turn-5 {{ background: #6f42c1; }}
        .timeline-marker.turn-6 {{ background: #20c997; }}
        .timeline-marker.turn-7 {{ background: #fd7e14; }}
        .timeline-marker.turn-8 {{ background: #e83e8c; }}
        .timeline-marker.turn-9 {{ background: #17a2b8; }}
        .timeline-marker.turn-10 {{ background: #6c757d; }}
        .timeline-content {{
            flex: 1;
        }}
        .timeline-header {{
            display: flex;
            gap: 10px;
            align-items: center;
            margin-bottom: 5px;
        }}
        .tool-name {{
            font-weight: 600;
            color: #1a1a1a;
        }}
        .turn-badge {{
            font-size: 11px;
            padding: 2px 8px;
            background: #e9ecef;
            border-radius: 10px;
            color: #495057;
        }}
        .duration {{
            font-size: 12px;
            color: #6c757d;
            margin-left: auto;
        }}
        .timeline-preview {{
            font-size: 13px;
            color: #666;
        }}
        .turn-card {{
            padding: 15px;
            background: #f8f9fa;
            border-radius: 6px;
            margin-bottom: 10px;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .turn-card:hover {{
            background: #e9ecef;
            transform: translateY(-2px);
        }}
        .turn-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }}
        .turn-header h3 {{
            font-size: 16px;
            color: #1a1a1a;
        }}
        .turn-meta {{
            font-size: 12px;
            color: #6c757d;
        }}
        .turn-tools {{
            font-size: 13px;
            color: #666;
        }}
        .tool-stats-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .tool-stats-table th {{
            text-align: left;
            padding: 10px;
            background: #f8f9fa;
            font-size: 12px;
            font-weight: 600;
            color: #495057;
        }}
        .tool-stats-table td {{
            padding: 10px;
            border-top: 1px solid #e9ecef;
            font-size: 13px;
        }}
        .tool-bar {{
            background: #007bff;
            height: 24px;
            border-radius: 4px;
            display: inline-block;
            min-width: 2px;
        }}
        .details-panel {{
            position: sticky;
            top: 20px;
            max-height: calc(100vh - 40px);
            overflow-y: auto;
        }}
        .details-empty {{
            color: #999;
            text-align: center;
            padding: 40px 20px;
            font-style: italic;
        }}
        .details-header {{
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e9ecef;
        }}
        .details-title {{
            font-size: 16px;
            font-weight: 600;
            color: #1a1a1a;
        }}
        .selected {{
            background: #e7f3ff !important;
            border-left: 3px solid #007bff;
        }}
        pre {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
            overflow-x: auto;
            font-size: 13px;
            line-height: 1.4;
        }}
        code {{
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        }}
        .detail-section {{
            margin-bottom: 20px;
        }}
        .detail-section h3 {{
            font-size: 14px;
            color: #495057;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .task-description {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #007bff;
            margin-top: 15px;
            font-size: 14px;
            white-space: pre-wrap;
            font-family: monospace;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Session: {escape_html(session_id)}</h1>
            <div class="session-meta">
                Model: <strong>{escape_html(model)}</strong> |
                Started: <strong>{started_at[:19] if started_at else "N/A"}</strong> |
                Completed: <strong>{completed_at[:19] if completed_at else "N/A"}</strong>
                <span class="status-badge status-{'success' if success else 'failure'}">
                    {'SUCCESS' if success else 'FAILURE'}
                </span>
            </div>
            <div class="task-description">{escape_html(task)}</div>
        </header>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Total Turns</div>
                <div class="stat-value">{total_turns}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Tool Calls</div>
                <div class="stat-value">{stats['total_calls']}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Input Tokens</div>
                <div class="stat-value">{usage.get('input_tokens', 0):,}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Output Tokens</div>
                <div class="stat-value">{usage.get('output_tokens', 0):,}</div>
            </div>
        </div>

        <div class="grid">
            <div class="panel">
                <h2>Turns</h2>
                {''.join(turn_summaries)}
            </div>

            <div class="panel">
                <h2>Timeline</h2>
                <div class="timeline">
                    {''.join(timeline_html)}
                </div>
            </div>

            <div class="panel details-panel">
                <h2>Details</h2>
                <div id="detailsContent" class="details-empty">
                    Click on any turn or timeline entry to see details
                </div>
            </div>
        </div>

        <div class="panel">
            <h2>Tool Usage Statistics</h2>
            <table class="tool-stats-table">
                <thead>
                    <tr>
                        <th>Tool</th>
                        <th>Count</th>
                        <th>Avg Duration</th>
                        <th>Total Duration</th>
                        <th>Usage</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join([f'''
                    <tr>
                        <td><strong>{escape_html(item['tool'])}</strong></td>
                        <td>{item['count']}</td>
                        <td>{format_duration(item['avg_duration'])}</td>
                        <td>{format_duration(item['total_duration'])}</td>
                        <td>
                            <div class="tool-bar" style="width: {min(300, item['count'] * 20)}px;"></div>
                        </td>
                    </tr>
                    ''' for item in tool_chart_data])}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        const timelineData = {json.dumps(timeline)};
        const turnData = {json.dumps(turns)};
        let currentSelection = null;

        function showToolDetails(index) {{
            const entry = timelineData[index];
            const content = document.getElementById('detailsContent');

            // Remove previous selection highlight
            if (currentSelection) {{
                currentSelection.classList.remove('selected');
            }}

            // Highlight current selection
            const timelineEntries = document.querySelectorAll('.timeline-entry');
            if (timelineEntries[index]) {{
                timelineEntries[index].classList.add('selected');
                currentSelection = timelineEntries[index];
            }}

            let html = `
                <div class="details-header">
                    <div class="details-title">Tool: ${{entry.tool}} (Turn ${{entry.turn}})</div>
                </div>
                <div class="detail-section">
                    <h3>Timestamp</h3>
                    <p>${{entry.timestamp}}</p>
                </div>
                <div class="detail-section">
                    <h3>Duration</h3>
                    <p>${{formatDuration(entry.duration_ms || 0)}}</p>
                </div>
            `;

            if (entry.args) {{
                html += `
                    <div class="detail-section">
                        <h3>Arguments</h3>
                        <pre><code>${{escapeHtml(JSON.stringify(entry.args, null, 2))}}</code></pre>
                    </div>
                `;
            }}

            if (entry.result_preview) {{
                html += `
                    <div class="detail-section">
                        <h3>Result</h3>
                        <pre><code>${{escapeHtml(entry.result_preview)}}</code></pre>
                    </div>
                `;
            }}

            content.innerHTML = html;
            content.classList.remove('details-empty');
        }}

        function showTurnDetails(index) {{
            const turn = turnData[index];
            const content = document.getElementById('detailsContent');

            // Remove previous selection highlight
            if (currentSelection) {{
                currentSelection.classList.remove('selected');
            }}

            // Highlight current selection
            const turnCards = document.querySelectorAll('.turn-card');
            if (turnCards[index]) {{
                turnCards[index].classList.add('selected');
                currentSelection = turnCards[index];
            }}

            let html = `
                <div class="details-header">
                    <div class="details-title">Turn ${{turn.turn}}</div>
                </div>
                <div class="detail-section">
                    <h3>Duration</h3>
                    <p>${{turn.duration_s || 0}} seconds</p>
                </div>
                <div class="detail-section">
                    <h3>Tool Calls (${{turn.tool_calls.length}})</h3>
                    <ul>
                        ${{turn.tool_calls.map(tc => `
                            <li><strong>${{tc.tool}}</strong>: ${{truncate(tc.result_preview || 'No preview', 100)}}</li>
                        `).join('')}}
                    </ul>
                </div>
            `;

            if (turn.text_output) {{
                html += `
                    <div class="detail-section">
                        <h3>Text Output</h3>
                        <pre><code>${{escapeHtml(turn.text_output)}}</code></pre>
                    </div>
                `;
            }}

            content.innerHTML = html;
            content.classList.remove('details-empty');
        }}

        function escapeHtml(text) {{
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}

        function formatDuration(ms) {{
            if (ms < 1000) return `${{ms.toFixed(0)}}ms`;
            if (ms < 60000) return `${{(ms/1000).toFixed(1)}}s`;
            return `${{(ms/60000).toFixed(1)}}min`;
        }}

        function truncate(text, maxLen) {{
            if (text.length <= maxLen) return text;
            return text.substring(0, maxLen) + '...';
        }}
    </script>
</body>
</html>'''

    return html

def main():
    if len(sys.argv) < 2:
        print("Usage: python visualize_session.py <session_dir> [output.html]")
        print("\nExample:")
        print("  python visualize_session.py eval_results/test_run/aimeII_2001_p3/20260424-015729/")
        sys.exit(1)

    session_dir = Path(sys.argv[1])
    if not session_dir.exists():
        print(f"Error: Directory not found: {session_dir}")
        sys.exit(1)

    output_file = sys.argv[2] if len(sys.argv) > 2 else "session_visualization.html"

    print(f"Loading session data from {session_dir}...")
    data = load_session_data(session_dir)

    print(f"Generating HTML visualization...")
    html = generate_html(data, session_dir)

    output_path = Path(output_file)
    with open(output_path, 'w') as f:
        f.write(html)

    print(f"✓ Visualization saved to: {output_path.absolute()}")
    print(f"\nOpen in browser: file://{output_path.absolute()}")

if __name__ == "__main__":
    main()
