#!/usr/bin/env python3
"""
Generate HTML visualizations for all LEA agent sessions in a directory.

Usage:
    python visualize_all_sessions.py <eval_results_dir> [output_dir]

Example:
    python visualize_all_sessions.py eval_results/test_run/ visualizations/
"""

import sys
import json
import subprocess
from pathlib import Path

def find_session_dirs(base_dir: Path):
    """Find all session directories (those with metadata.json)."""
    sessions = []
    for metadata_file in base_dir.rglob("metadata.json"):
        session_dir = metadata_file.parent
        sessions.append(session_dir)
    return sorted(sessions)

def main():
    if len(sys.argv) < 2:
        print("Usage: python visualize_all_sessions.py <eval_results_dir> [output_dir]")
        print("\nExample:")
        print("  python visualize_all_sessions.py eval_results/test_run/ visualizations/")
        sys.exit(1)

    base_dir = Path(sys.argv[1])
    if not base_dir.exists():
        print(f"Error: Directory not found: {base_dir}")
        sys.exit(1)

    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("visualizations")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Scanning for sessions in {base_dir}...")
    sessions = find_session_dirs(base_dir)
    print(f"Found {len(sessions)} sessions\n")

    for i, session_dir in enumerate(sessions, 1):
        # Create a meaningful output filename
        problem_name = session_dir.parent.name
        session_id = session_dir.name
        output_file = output_dir / f"{problem_name}_{session_id}.html"

        print(f"[{i}/{len(sessions)}] Processing {problem_name}/{session_id}...")

        try:
            subprocess.run([
                "python", "eval/visualize_session.py",
                str(session_dir),
                str(output_file)
            ], check=True, capture_output=True, text=True)
            print(f"  ✓ Saved to {output_file}")
        except subprocess.CalledProcessError as e:
            print(f"  ✗ Error: {e.stderr}")

    print(f"\n✓ Generated {len(sessions)} visualizations in {output_dir.absolute()}")

    # Create an index.html
    create_index(output_dir, sessions)

def create_index(output_dir: Path, sessions: list):
    """Create an index.html listing all visualizations."""
    from datetime import datetime

    # Load session data for table
    session_data = []
    for session_dir in sessions:
        final_result_file = session_dir / "final_result.json"
        metadata_file = session_dir / "metadata.json"

        if not final_result_file.exists():
            continue

        with open(final_result_file) as f:
            final_result = json.load(f)

        metadata = {}
        if metadata_file.exists():
            with open(metadata_file) as f:
                metadata = json.load(f)

        problem_name = session_dir.parent.name
        session_id = final_result.get("session_id", session_dir.name)

        usage = final_result.get("usage", {})
        total_tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

        # Calculate duration
        started_at = metadata.get("started_at", "")
        completed_at = final_result.get("completed_at", "")
        duration_str = ""
        if started_at and completed_at:
            try:
                start = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                end = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                duration_sec = (end - start).total_seconds()
                if duration_sec < 60:
                    duration_str = f"{duration_sec:.0f}s"
                elif duration_sec < 3600:
                    duration_str = f"{duration_sec/60:.1f}m"
                else:
                    duration_str = f"{duration_sec/3600:.1f}h"
            except:
                duration_str = "N/A"

        session_data.append({
            "problem": problem_name,
            "session_id": session_id,
            "success": final_result.get("success", False),
            "turns": final_result.get("turns", 0),
            "tokens": total_tokens,
            "duration": duration_str,
            "html_file": f"{problem_name}_{session_id}.html"
        })

    # Calculate summary stats
    total_sessions = len(session_data)
    passed = sum(1 for s in session_data if s["success"])
    failed = total_sessions - passed
    success_rate = (passed / total_sessions * 100) if total_sessions > 0 else 0
    total_tokens = sum(s["tokens"] for s in session_data)
    unique_problems = len(set(s["problem"] for s in session_data))

    # Sort by most recent first (session_id is timestamp-based)
    session_data.sort(key=lambda x: x["session_id"], reverse=True)

    index_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LEA Session Visualizations</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.6;
            padding: 40px 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        h1 {
            margin-bottom: 10px;
            color: #1a1a1a;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 16px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 6px;
            border-left: 4px solid #007bff;
        }
        .stat-label {
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 5px;
        }
        .stat-value {
            font-size: 28px;
            font-weight: 700;
            color: #1a1a1a;
        }
        .stat-subtext {
            font-size: 13px;
            color: #666;
            margin-top: 5px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            font-size: 14px;
        }
        thead {
            background: #f8f9fa;
        }
        th {
            text-align: left;
            padding: 12px 16px;
            font-weight: 600;
            color: #495057;
            border-bottom: 2px solid #dee2e6;
        }
        th.text-right, td.text-right {
            text-align: right;
        }
        th.text-center, td.text-center {
            text-align: center;
        }
        td {
            padding: 12px 16px;
            border-bottom: 1px solid #e9ecef;
        }
        tr:hover {
            background: #f8f9fa;
        }
        .status-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }
        .status-pass {
            background: #d4edda;
            color: #155724;
        }
        .status-fail {
            background: #f8d7da;
            color: #721c24;
        }
        .problem-link {
            color: #007bff;
            text-decoration: none;
            font-weight: 500;
        }
        .problem-link:hover {
            text-decoration: underline;
        }
        .session-id {
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 12px;
            color: #666;
        }
        .sortable {
            cursor: pointer;
            user-select: none;
        }
        .sortable:hover {
            background: #e9ecef;
        }
        .sortable::after {
            content: ' ↕';
            opacity: 0.3;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>LEA Session Visualizations</h1>
        <p class="subtitle">Interactive analysis of theorem proving sessions</p>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Total Sessions</div>
                <div class="stat-value">''' + str(total_sessions) + '''</div>
                <div class="stat-subtext">''' + str(unique_problems) + ''' unique problems</div>
            </div>
            <div class="stat-card" style="border-left-color: #28a745;">
                <div class="stat-label">Success Rate</div>
                <div class="stat-value">''' + f'{success_rate:.1f}%' + '''</div>
                <div class="stat-subtext">''' + str(passed) + ' passed, ' + str(failed) + ''' failed</div>
            </div>
            <div class="stat-card" style="border-left-color: #ffc107;">
                <div class="stat-label">Total Tokens</div>
                <div class="stat-value">''' + f'{total_tokens/1e6:.2f}M' + '''</div>
                <div class="stat-subtext">''' + f'{total_tokens/total_sessions:,.0f}' + ''' avg/session</div>
            </div>
        </div>

        <table id="sessionsTable">
            <thead>
                <tr>
                    <th class="sortable" onclick="sortTable(0)">Problem</th>
                    <th class="sortable text-center" onclick="sortTable(1)">Result</th>
                    <th class="sortable text-right" onclick="sortTable(2)">Turns</th>
                    <th class="sortable text-right" onclick="sortTable(3)">Tokens</th>
                    <th class="sortable text-right" onclick="sortTable(4)">Duration</th>
                    <th class="sortable" onclick="sortTable(5)">Session</th>
                </tr>
            </thead>
            <tbody>
'''

    for session in session_data:
        status_class = "status-pass" if session["success"] else "status-fail"
        status_text = "PASS" if session["success"] else "FAIL"

        index_html += f'''                <tr>
                    <td><a href="{session['html_file']}" class="problem-link">{session['problem']}</a></td>
                    <td class="text-center"><span class="status-badge {status_class}">{status_text}</span></td>
                    <td class="text-right">{session['turns']}</td>
                    <td class="text-right">{session['tokens']:,}</td>
                    <td class="text-right">{session['duration']}</td>
                    <td><span class="session-id">{session['session_id']}</span></td>
                </tr>
'''

    index_html += '''            </tbody>
        </table>
    </div>

    <script>
        let sortDirection = {};

        function sortTable(columnIndex) {
            const table = document.getElementById('sessionsTable');
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));

            // Toggle sort direction
            sortDirection[columnIndex] = !sortDirection[columnIndex];
            const ascending = sortDirection[columnIndex];

            rows.sort((a, b) => {
                let aValue = a.cells[columnIndex].textContent.trim();
                let bValue = b.cells[columnIndex].textContent.trim();

                // Handle numeric columns
                if (columnIndex === 2 || columnIndex === 3) { // Turns or Tokens
                    aValue = parseInt(aValue.replace(/,/g, ''));
                    bValue = parseInt(bValue.replace(/,/g, ''));
                    return ascending ? aValue - bValue : bValue - aValue;
                }

                // Handle duration
                if (columnIndex === 4) {
                    const parseTime = (str) => {
                        if (!str || str === 'N/A') return 0;
                        const match = str.match(/([\d.]+)([smh])/);
                        if (!match) return 0;
                        const value = parseFloat(match[1]);
                        const unit = match[2];
                        if (unit === 's') return value;
                        if (unit === 'm') return value * 60;
                        if (unit === 'h') return value * 3600;
                        return 0;
                    };
                    aValue = parseTime(aValue);
                    bValue = parseTime(bValue);
                    return ascending ? aValue - bValue : bValue - aValue;
                }

                // String comparison
                return ascending
                    ? aValue.localeCompare(bValue)
                    : bValue.localeCompare(aValue);
            });

            // Re-append rows
            rows.forEach(row => tbody.appendChild(row));
        }
    </script>
</body>
</html>'''

    index_file = output_dir / "index.html"
    with open(index_file, 'w') as f:
        f.write(index_html)

    print(f"✓ Created index at {index_file.absolute()}")
    print(f"\nOpen index: file://{index_file.absolute()}")

if __name__ == "__main__":
    main()
