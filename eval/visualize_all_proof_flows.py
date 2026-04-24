#!/usr/bin/env python3
"""
Generate proof flow visualizations for all sessions with snapshots.

Usage:
    python visualize_all_proof_flows.py [base_dir] [output_dir]

Example:
    python visualize_all_proof_flows.py eval_results visualizations/proof_flow
"""

import sys
from pathlib import Path
import subprocess


def find_session_directories(base_dir: Path) -> list[Path]:
    """Find all session directories that have snapshots."""
    session_dirs = []

    for session_dir in base_dir.rglob("*"):
        if session_dir.is_dir() and (session_dir / "snapshots").exists():
            # Check if snapshots directory has content
            snapshots_dir = session_dir / "snapshots"
            if any(snapshots_dir.iterdir()):
                session_dirs.append(session_dir)

    return sorted(session_dirs)


def main():
    base_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("eval_results")
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("visualizations/proof_flow")

    if not base_dir.exists():
        print(f"Error: Base directory not found: {base_dir}")
        sys.exit(1)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Searching for sessions in {base_dir}...")
    session_dirs = find_session_directories(base_dir)

    if not session_dirs:
        print("No sessions with snapshots found!")
        sys.exit(1)

    print(f"Found {len(session_dirs)} sessions with snapshots\n")

    success_count = 0
    fail_count = 0

    for i, session_dir in enumerate(session_dirs, 1):
        # Create output filename from session path
        relative_path = session_dir.relative_to(base_dir)
        # Replace path separators with underscores
        output_name = str(relative_path).replace("/", "_") + ".html"
        output_file = output_dir / output_name

        print(f"[{i}/{len(session_dirs)}] Processing {relative_path}...")

        try:
            # Run visualize_proof_flow.py
            result = subprocess.run(
                ["python", "eval/visualize_proof_flow.py", str(session_dir), str(output_file)],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                print(f"  ✓ Generated {output_file.name}")
                success_count += 1
            else:
                print(f"  ✗ Failed: {result.stderr.strip()}")
                fail_count += 1

        except subprocess.TimeoutExpired:
            print(f"  ✗ Timeout")
            fail_count += 1
        except Exception as e:
            print(f"  ✗ Error: {e}")
            fail_count += 1

    print(f"\n{'='*60}")
    print(f"Complete: {success_count} succeeded, {fail_count} failed")
    print(f"Output directory: {output_dir.absolute()}")

    # Generate an index.html
    generate_index(output_dir, session_dirs, output_dir)


def generate_index(output_dir: Path, session_dirs: list[Path], vis_dir: Path):
    """Generate an index.html file listing all proof flow visualizations."""

    html_files = sorted(vis_dir.glob("*.html"))

    if not html_files:
        return

    index_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Proof Flow Visualizations</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            padding: 40px 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            margin-bottom: 10px;
            color: #1a1a1a;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
        }
        .description {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 6px;
            margin-bottom: 30px;
            border-left: 4px solid #007bff;
        }
        .description h2 {
            font-size: 16px;
            margin-bottom: 10px;
            color: #1a1a1a;
        }
        .description p {
            font-size: 14px;
            color: #666;
            line-height: 1.6;
        }
        .description ul {
            margin: 10px 0 10px 20px;
            font-size: 14px;
            color: #666;
        }
        .session-list {
            list-style: none;
        }
        .session-item {
            margin-bottom: 15px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 6px;
            transition: background 0.2s;
        }
        .session-item:hover {
            background: #e9ecef;
        }
        .session-link {
            color: #007bff;
            text-decoration: none;
            font-size: 16px;
            font-weight: 500;
        }
        .session-link:hover {
            text-decoration: underline;
        }
        .session-path {
            color: #6c757d;
            font-size: 13px;
            margin-top: 5px;
            font-family: monospace;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Proof Flow Visualizations</h1>
        <div class="subtitle">Block-based flow diagrams showing proof evolution across snapshots</div>

        <div class="description">
            <h2>What is this?</h2>
            <p>These visualizations show how Lean proofs evolve during agent execution using a block-based flow design:</p>
            <ul>
                <li><strong>Blocks</strong>: Consecutive lines of the same type (added/deleted/modified/unchanged) are grouped</li>
                <li><strong>Flows</strong>: Curved connections show how blocks transform between snapshots</li>
                <li><strong>Colors</strong>: Grey=unchanged, Yellow=modified, Green=added, Red=deleted</li>
                <li><strong>Interactive</strong>: Hover blocks to see full code and highlight flows</li>
            </ul>
            <p style="margin-top: 10px;">
                Example: Instead of showing 30 individual line boxes, a proof might show 6 blocks
                (8-line imports block, 3-line modified block, etc.), making structure instantly visible.
            </p>
        </div>

        <ul class="session-list">
"""

    for html_file in html_files:
        if html_file.name == "index.html":
            continue

        # Extract session name from filename
        session_name = html_file.stem

        index_html += f"""
            <li class="session-item">
                <a href="{html_file.name}" class="session-link">{session_name}</a>
                <div class="session-path">{html_file.name}</div>
            </li>
"""

    index_html += """
        </ul>
    </div>
</body>
</html>
"""

    index_path = vis_dir / "index.html"
    with open(index_path, 'w') as f:
        f.write(index_html)

    print(f"\n✓ Generated index: {index_path}")


if __name__ == "__main__":
    main()
