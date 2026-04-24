#!/usr/bin/env python3
"""
Generate flow-based proof evolution visualization with block grouping.

This creates a matrix-like visualization where:
- Columns = snapshots
- Blocks = consecutive lines of same type (added/deleted/modified/unchanged)
- Boxes contain actual text from multiple lines
- Connections show block transformations (like a Sankey diagram)

Inspired by History Flow and alluvial diagrams.

Usage:
    python visualize_proof_flow.py <session_dir> [output.html]

Example:
    python visualize_proof_flow.py eval_results/test_run/aime_1990_p2/20260424-025516/
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import difflib
from datetime import datetime


def load_snapshots(session_dir: Path) -> List[Dict[str, Any]]:
    """Load all snapshots from the session directory."""
    snapshots_dir = session_dir / "snapshots"
    if not snapshots_dir.exists():
        return []

    snapshots = []
    snapshot_dirs = sorted(snapshots_dir.iterdir(), key=lambda p: _snapshot_sort_key(p.name))

    for snapshot_dir in snapshot_dirs:
        if not snapshot_dir.is_dir():
            continue

        snapshot_info_file = snapshot_dir / "snapshot_info.json"
        if not snapshot_info_file.exists():
            continue

        with open(snapshot_info_file) as f:
            snapshot_info = json.load(f)

        # Load .lean file content
        files_content = {}
        for file_info in snapshot_info.get("files", []):
            file_path = snapshot_dir / file_info["path"]
            if file_path.exists() and file_path.suffix == ".lean":
                with open(file_path) as f:
                    files_content[file_info["path"]] = f.read()

        snapshots.append({
            "name": snapshot_dir.name,
            "info": snapshot_info,
            "files": files_content
        })

    return snapshots


def _snapshot_sort_key(name: str) -> tuple:
    """Sort key for snapshot directories."""
    if name == "before":
        return (0, 0)
    elif name == "after":
        return (999999, 0)
    elif name.startswith("turn_"):
        try:
            turn_num = int(name.split("_")[1])
            return (turn_num, 0)
        except (IndexError, ValueError):
            return (999998, 0)
    return (999997, 0)


def compute_flow_data(snapshots: List[Dict[str, Any]], filename: str) -> Dict[str, Any]:
    """
    Compute flow data for visualization with block grouping.

    Returns structure with:
    - snapshots: list of snapshot data with blocks (grouped consecutive lines of same type)
    - flows: list of flow connections between blocks across snapshots
    """
    snapshot_data = []

    for snapshot in snapshots:
        if filename not in snapshot["files"]:
            continue

        content = snapshot["files"][filename]
        lines = content.splitlines()

        snapshot_data.append({
            "name": snapshot["name"],
            "turn": snapshot["info"].get("turn", -1),
            "lines": lines,
            "line_count": len(lines),
            "blocks": []  # Will be populated after diff analysis
        })

    # First pass: Compute line-level diffs and assign types to each line
    line_types = []  # line_types[snapshot_idx][line_idx] = type

    for i, snapshot in enumerate(snapshot_data):
        line_types.append(['unknown'] * len(snapshot["lines"]))

    # Analyze diffs between consecutive snapshots
    for i in range(len(snapshot_data) - 1):
        source_snapshot = snapshot_data[i]
        target_snapshot = snapshot_data[i + 1]
        source_lines = source_snapshot["lines"]
        target_lines = target_snapshot["lines"]

        matcher = difflib.SequenceMatcher(None, source_lines, target_lines)

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                # Mark as unchanged
                for offset in range(i2 - i1):
                    line_types[i][i1 + offset] = 'equal'
                    line_types[i + 1][j1 + offset] = 'equal'
            elif tag == 'replace':
                # Mark as modified
                for offset in range(i2 - i1):
                    if line_types[i][i1 + offset] == 'unknown':
                        line_types[i][i1 + offset] = 'modified'
                for offset in range(j2 - j1):
                    if line_types[i + 1][j1 + offset] == 'unknown':
                        line_types[i + 1][j1 + offset] = 'modified'
            elif tag == 'delete':
                for offset in range(i2 - i1):
                    if line_types[i][i1 + offset] == 'unknown':
                        line_types[i][i1 + offset] = 'deleted'
            elif tag == 'insert':
                for offset in range(j2 - j1):
                    if line_types[i + 1][j1 + offset] == 'unknown':
                        line_types[i + 1][j1 + offset] = 'added'

    # Fix any remaining 'unknown' (shouldn't happen, but be safe)
    for i in range(len(line_types)):
        for j in range(len(line_types[i])):
            if line_types[i][j] == 'unknown':
                line_types[i][j] = 'equal'

    # Second pass: Group consecutive lines of same type into blocks
    for i, snapshot in enumerate(snapshot_data):
        blocks = []
        current_block = None

        for line_idx, line in enumerate(snapshot["lines"]):
            line_type = line_types[i][line_idx]

            if current_block is None or current_block["type"] != line_type:
                # Start new block
                if current_block is not None:
                    blocks.append(current_block)

                current_block = {
                    "type": line_type,
                    "start_line": line_idx,
                    "end_line": line_idx,
                    "lines": [line],
                    "line_count": 1
                }
            else:
                # Extend current block
                current_block["end_line"] = line_idx
                current_block["lines"].append(line)
                current_block["line_count"] += 1

        if current_block is not None:
            blocks.append(current_block)

        snapshot["blocks"] = blocks

    # Third pass: Compute block-level flows
    flows = []
    processed_pairs = set()  # Track (source_block_idx, target_block_idx) pairs

    for i in range(len(snapshot_data) - 1):
        source_snapshot = snapshot_data[i]
        target_snapshot = snapshot_data[i + 1]
        source_lines = source_snapshot["lines"]
        target_lines = target_snapshot["lines"]

        matcher = difflib.SequenceMatcher(None, source_lines, target_lines)

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal' or tag == 'replace':
                # Find blocks in source and target
                if i1 < len(source_lines):
                    source_block_idx = _find_block_containing_line(source_snapshot["blocks"], i1)
                else:
                    source_block_idx = None

                if j1 < len(target_lines):
                    target_block_idx = _find_block_containing_line(target_snapshot["blocks"], j1)
                else:
                    target_block_idx = None

                if source_block_idx is not None and target_block_idx is not None:
                    pair = (source_block_idx, target_block_idx)
                    if pair not in processed_pairs:
                        flows.append({
                            "source_snapshot": i,
                            "target_snapshot": i + 1,
                            "source_block": source_block_idx,
                            "target_block": target_block_idx,
                            "type": tag if tag == 'replace' else 'equal'
                        })
                        processed_pairs.add(pair)

            elif tag == 'delete':
                if i1 < len(source_lines):
                    source_block_idx = _find_block_containing_line(source_snapshot["blocks"], i1)
                    if source_block_idx is not None:
                        flows.append({
                            "source_snapshot": i,
                            "target_snapshot": i + 1,
                            "source_block": source_block_idx,
                            "target_block": None,
                            "type": "deleted"
                        })

            elif tag == 'insert':
                if j1 < len(target_lines):
                    target_block_idx = _find_block_containing_line(target_snapshot["blocks"], j1)
                    if target_block_idx is not None:
                        flows.append({
                            "source_snapshot": i,
                            "target_snapshot": i + 1,
                            "source_block": None,
                            "target_block": target_block_idx,
                            "type": "added"
                        })

    return {
        "snapshots": snapshot_data,
        "flows": flows
    }


def _find_block_containing_line(blocks: List[Dict], line_idx: int) -> Optional[int]:
    """Find the block index that contains the given line index."""
    for i, block in enumerate(blocks):
        if block["start_line"] <= line_idx <= block["end_line"]:
            return i
    return None


def generate_html(session_dir: Path, snapshots: List[Dict[str, Any]]) -> str:
    """Generate the flow-based proof evolution visualization."""

    # Find primary .lean file
    primary_file = None
    for snapshot in snapshots:
        if snapshot["files"]:
            primary_file = list(snapshot["files"].keys())[0]
            break

    if not primary_file:
        return "<html><body>No .lean files found in snapshots</body></html>"

    # Compute flow data
    flow_data = compute_flow_data(snapshots, primary_file)

    # Load session metadata
    metadata_file = session_dir / "metadata.json"
    metadata = {}
    if metadata_file.exists():
        with open(metadata_file) as f:
            metadata = json.load(f)

    session_id = metadata.get("session_id", session_dir.name)
    task = metadata.get("task", "")

    # Convert to JSON
    flow_data_json = json.dumps(flow_data, indent=2)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Proof Flow - {session_id}</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            color: #333;
        }}

        .container {{
            max-width: 100%;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }}

        header {{
            background: white;
            padding: 20px 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            z-index: 100;
        }}

        h1 {{
            font-size: 24px;
            margin-bottom: 10px;
        }}

        .task-description {{
            font-size: 14px;
            color: #666;
            font-style: italic;
        }}

        .controls {{
            display: flex;
            gap: 15px;
            align-items: center;
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #e9ecef;
        }}

        .control-group {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        label {{
            font-size: 14px;
            color: #666;
        }}

        input[type="range"] {{
            width: 150px;
        }}

        select, button {{
            padding: 6px 12px;
            border: 1px solid #ccc;
            border-radius: 4px;
            background: white;
            cursor: pointer;
            font-size: 14px;
        }}

        button:hover {{
            background: #f8f9fa;
        }}

        #visualization {{
            flex: 1;
            overflow: auto;
            background: white;
            position: relative;
        }}

        .block-box {{
            stroke: #333;
            stroke-width: 1.5;
            cursor: pointer;
        }}

        .block-box.equal {{
            fill: #f8f9fa;
        }}

        .block-box.added {{
            fill: #d4edda;
        }}

        .block-box.deleted {{
            fill: #f8d7da;
        }}

        .block-box.modified {{
            fill: #fff3cd;
        }}

        .block-box:hover {{
            stroke: #007bff;
            stroke-width: 3;
        }}

        .block-box.highlighted {{
            stroke: #007bff;
            stroke-width: 3;
        }}

        .block-text {{
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 10px;
            pointer-events: none;
            user-select: none;
        }}

        .block-label {{
            font-size: 10px;
            fill: #666;
            font-weight: 600;
            pointer-events: none;
        }}

        .flow-path {{
            fill: none;
            stroke-width: 2;
            opacity: 0.3;
        }}

        .flow-path.equal {{
            stroke: #6c757d;
        }}

        .flow-path.added {{
            stroke: #28a745;
        }}

        .flow-path.deleted {{
            stroke: #dc3545;
        }}

        .flow-path.modified,
        .flow-path.replace {{
            stroke: #ffc107;
        }}

        .flow-path:hover,
        .flow-path.highlighted {{
            opacity: 0.8;
            stroke-width: 4;
        }}

        .snapshot-label {{
            font-size: 14px;
            font-weight: 600;
            fill: #333;
        }}

        .snapshot-meta {{
            font-size: 10px;
            fill: #666;
        }}

        .tooltip {{
            position: absolute;
            background: rgba(0, 0, 0, 0.9);
            color: white;
            padding: 10px 14px;
            border-radius: 4px;
            font-size: 12px;
            pointer-events: none;
            z-index: 1000;
            display: none;
            max-width: 500px;
            font-family: 'Monaco', 'Menlo', monospace;
            white-space: pre;
            line-height: 1.4;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Proof Flow Evolution: {primary_file}</h1>
            <div class="task-description">{task}</div>

            <div class="controls">
                <div class="control-group">
                    <label for="lineHeight">Line Height:</label>
                    <input type="range" id="lineHeight" min="15" max="40" value="22" step="1">
                    <span id="lineHeightValue">22px</span>
                </div>

                <div class="control-group">
                    <label for="boxWidth">Box Width:</label>
                    <input type="range" id="boxWidth" min="250" max="700" value="450" step="50">
                    <span id="boxWidthValue">450px</span>
                </div>

                <div class="control-group">
                    <label>
                        <input type="checkbox" id="showFlows" checked> Show Flows
                    </label>
                </div>

                <div class="control-group">
                    <label>
                        <input type="checkbox" id="showUnchanged" checked> Show Unchanged
                    </label>
                </div>
            </div>
        </header>

        <div id="visualization"></div>
    </div>

    <div class="tooltip" id="tooltip"></div>

    <script>
        // Data
        const flowData = {flow_data_json};

        // Configuration
        let config = {{
            lineHeight: 18,
            boxWidth: 450,
            blockPadding: 8,
            snapshotGap: 120,
            headerHeight: 80,
            padding: 40,
            showFlows: true,
            showUnchanged: true,
            maxLinesInBlock: 999  // Max lines to show in a block before truncating
        }};

        // State
        let highlightedFlow = null;

        // Initialize
        render();
        setupEventListeners();

        function render() {{
            const viz = d3.select('#visualization');
            viz.html('');

            // Calculate block heights for layout
            flowData.snapshots.forEach(snapshot => {{
                snapshot.blocks.forEach(block => {{
                    // Calculate height for all lines
                    block.height = block.line_count * config.lineHeight + config.blockPadding * 2 + 20;
                }});
            }});

            // Calculate total height
            const maxTotalHeight = d3.max(flowData.snapshots, snapshot => {{
                return d3.sum(snapshot.blocks, b => b.height + 10);
            }});

            const totalWidth = flowData.snapshots.length * (config.boxWidth + config.snapshotGap) + config.padding * 2;
            const totalHeight = maxTotalHeight + config.headerHeight + config.padding * 2;

            // Create SVG
            const svg = viz.append('svg')
                .attr('width', totalWidth)
                .attr('height', totalHeight);

            const g = svg.append('g')
                .attr('transform', `translate(${{config.padding}}, ${{config.padding}})`);

            // Draw flows first (behind blocks)
            const flowsGroup = g.append('g').attr('class', 'flows');

            if (config.showFlows) {{
                flowData.flows.forEach((flow, flowIdx) => {{
                    if (flow.type === 'equal' && !config.showUnchanged) {{
                        return;
                    }}

                    if (flow.source_block !== null && flow.target_block !== null) {{
                        const sourceSnapshot = flowData.snapshots[flow.source_snapshot];
                        const targetSnapshot = flowData.snapshots[flow.target_snapshot];

                        const sourceBlock = sourceSnapshot.blocks[flow.source_block];
                        const targetBlock = targetSnapshot.blocks[flow.target_block];

                        // Calculate block positions
                        const sourceX = flow.source_snapshot * (config.boxWidth + config.snapshotGap) + config.boxWidth;
                        const sourceY = getBlockY(sourceSnapshot, flow.source_block) + sourceBlock.height / 2;

                        const targetX = flow.target_snapshot * (config.boxWidth + config.snapshotGap);
                        const targetY = getBlockY(targetSnapshot, flow.target_block) + targetBlock.height / 2;

                        const path = createCurvedPath(sourceX, sourceY, targetX, targetY);

                        flowsGroup.append('path')
                            .attr('d', path)
                            .attr('class', `flow-path ${{flow.type}}`)
                            .attr('data-flow-idx', flowIdx)
                            .on('mouseenter', () => highlightFlow(flowIdx))
                            .on('mouseleave', () => unhighlightFlow());
                    }}
                }});
            }}

            // Draw snapshots and blocks
            flowData.snapshots.forEach((snapshot, snapIdx) => {{
                const x = snapIdx * (config.boxWidth + config.snapshotGap);

                // Snapshot header
                g.append('text')
                    .attr('x', x + config.boxWidth / 2)
                    .attr('y', 20)
                    .attr('class', 'snapshot-label')
                    .attr('text-anchor', 'middle')
                    .text(snapshot.name);

                g.append('text')
                    .attr('x', x + config.boxWidth / 2)
                    .attr('y', 40)
                    .attr('class', 'snapshot-meta')
                    .attr('text-anchor', 'middle')
                    .text(`Turn ${{snapshot.turn}} • ${{snapshot.line_count}} lines • ${{snapshot.blocks.length}} blocks`);

                // Draw blocks
                snapshot.blocks.forEach((block, blockIdx) => {{
                    const y = getBlockY(snapshot, blockIdx);

                    // Draw block box
                    g.append('rect')
                        .attr('x', x)
                        .attr('y', y)
                        .attr('width', config.boxWidth)
                        .attr('height', block.height)
                        .attr('class', `block-box ${{block.type}}`)
                        .attr('data-snapshot', snapIdx)
                        .attr('data-block', blockIdx)
                        .on('mouseenter', function(event) {{
                            showTooltip(event, block);
                            highlightBlockFlows(snapIdx, blockIdx);
                        }})
                        .on('mouseleave', function() {{
                            hideTooltip();
                            unhighlightFlow();
                        }});

                    // Block type label (left)
                    g.append('text')
                        .attr('x', x + 8)
                        .attr('y', y + 13)
                        .attr('class', 'block-label')
                        .attr('text-anchor', 'start')
                        .style('font-weight', '700')
                        .style('text-transform', 'uppercase')
                        .style('font-size', '9px')
                        .text(`${{block.type}}`);

                    // Block line count label (right)
                    g.append('text')
                        .attr('x', x + config.boxWidth - 8)
                        .attr('y', y + 13)
                        .attr('class', 'block-label')
                        .attr('text-anchor', 'end')
                        .style('font-size', '9px')
                        .text(`${{block.line_count}} line${{block.line_count > 1 ? 's' : ''}}`);

                    // Draw lines
                    const visibleLines = Math.min(block.line_count, config.maxLinesInBlock);
                    for (let i = 0; i < visibleLines; i++) {{
                        const line = block.lines[i];
                        const truncatedText = line.length > 50 ? line.substring(0, 50) + '...' : line;

                        g.append('text')
                            .attr('x', x + 8)
                            .attr('y', y + config.blockPadding + 18 + (i + 1) * config.lineHeight - 4)
                            .attr('class', 'block-text')
                            .text(truncatedText);
                    }}

                    // If truncated, show ellipsis
                    if (block.line_count > visibleLines) {{
                        g.append('text')
                            .attr('x', x + 8)
                            .attr('y', y + config.blockPadding + 18 + (visibleLines + 0.5) * config.lineHeight)
                            .attr('class', 'block-text')
                            .style('font-style', 'italic')
                            .style('fill', '#999')
                            .text(`... ${{block.line_count - visibleLines}} more lines`);
                    }}
                }});
            }});
        }}

        function getBlockY(snapshot, blockIdx) {{
            let y = config.headerHeight;
            for (let i = 0; i < blockIdx; i++) {{
                y += snapshot.blocks[i].height + 10;  // 10px gap between blocks
            }}
            return y;
        }}

        function createCurvedPath(x1, y1, x2, y2) {{
            const midX = (x1 + x2) / 2;
            return `M ${{x1}} ${{y1}} C ${{midX}} ${{y1}}, ${{midX}} ${{y2}}, ${{x2}} ${{y2}}`;
        }}

        function highlightFlow(flowIdx) {{
            highlightedFlow = flowIdx;
            d3.selectAll('.flow-path').classed('highlighted', (d, i) => i === flowIdx);
        }}

        function highlightBlockFlows(snapIdx, blockIdx) {{
            // Find all flows involving this block
            const relevantFlowIndices = [];
            flowData.flows.forEach((flow, idx) => {{
                if ((flow.source_snapshot === snapIdx && flow.source_block === blockIdx) ||
                    (flow.target_snapshot === snapIdx && flow.target_block === blockIdx)) {{
                    relevantFlowIndices.push(idx);
                }}
            }});

            d3.selectAll('.flow-path')
                .classed('highlighted', function() {{
                    const idx = parseInt(d3.select(this).attr('data-flow-idx'));
                    return relevantFlowIndices.includes(idx);
                }});

            d3.selectAll('.block-box')
                .classed('highlighted', function() {{
                    const snap = parseInt(d3.select(this).attr('data-snapshot'));
                    const block = parseInt(d3.select(this).attr('data-block'));

                    return flowData.flows.some((flow, idx) => {{
                        if (!relevantFlowIndices.includes(idx)) return false;
                        return (flow.source_snapshot === snap && flow.source_block === block) ||
                               (flow.target_snapshot === snap && flow.target_block === block);
                    }});
                }});
        }}

        function unhighlightFlow() {{
            highlightedFlow = null;
            d3.selectAll('.flow-path').classed('highlighted', false);
            d3.selectAll('.block-box').classed('highlighted', false);
        }}

        function showTooltip(event, block) {{
            const tooltip = document.getElementById('tooltip');
            tooltip.style.display = 'block';

            // Show all lines in the block
            const text = block.lines.join('\\n');
            tooltip.textContent = `${{block.type.toUpperCase()}} (${{block.line_count}} lines)\\n${{text}}`;

            tooltip.style.left = (event.pageX + 10) + 'px';
            tooltip.style.top = (event.pageY + 10) + 'px';
        }}

        function hideTooltip() {{
            document.getElementById('tooltip').style.display = 'none';
        }}

        function setupEventListeners() {{
            document.getElementById('lineHeight').addEventListener('input', function(e) {{
                config.lineHeight = parseInt(e.target.value);
                document.getElementById('lineHeightValue').textContent = config.lineHeight + 'px';
                render();
            }});

            document.getElementById('boxWidth').addEventListener('input', function(e) {{
                config.boxWidth = parseInt(e.target.value);
                document.getElementById('boxWidthValue').textContent = config.boxWidth + 'px';
                render();
            }});

            document.getElementById('showFlows').addEventListener('change', function(e) {{
                config.showFlows = e.target.checked;
                render();
            }});

            document.getElementById('showUnchanged').addEventListener('change', function(e) {{
                config.showUnchanged = e.target.checked;
                render();
            }});
        }}
    </script>
</body>
</html>'''

    return html


def main():
    if len(sys.argv) < 2:
        print("Usage: python visualize_proof_flow.py <session_dir> [output.html]")
        print("\nExample:")
        print("  python visualize_proof_flow.py eval_results/test_run/aime_1990_p2/20260424-025516/")
        sys.exit(1)

    session_dir = Path(sys.argv[1])
    if not session_dir.exists():
        print(f"Error: Directory not found: {session_dir}")
        sys.exit(1)

    output_file = sys.argv[2] if len(sys.argv) > 2 else "proof_flow.html"

    print(f"Loading snapshots from {session_dir}...")
    snapshots = load_snapshots(session_dir)

    if not snapshots:
        print("Warning: No snapshots found!")
        sys.exit(1)

    print(f"Found {len(snapshots)} snapshots")

    print(f"Generating block-based flow visualization...")
    html = generate_html(session_dir, snapshots)

    output_path = Path(output_file)
    with open(output_path, 'w') as f:
        f.write(html)

    print(f"✓ Flow visualization saved to: {output_path.absolute()}")
    print(f"\nOpen in browser: file://{output_path.absolute()}")


if __name__ == "__main__":
    main()
