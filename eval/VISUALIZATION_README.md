# Session Visualization

Interactive HTML visualizations for LEA agent sessions.

## Quick Start

### Visualize a Single Session

```bash
python eval/visualize_session.py eval_results/test_run/aimeII_2001_p3/20260424-015729/ output.html
```

Then open `output.html` in your browser.

### Visualize All Sessions

```bash
python eval/visualize_all_sessions.py eval_results/test_run/ visualizations/
```

This will:
1. Find all sessions in `eval_results/test_run/`
2. Generate an HTML file for each session
3. Create an `index.html` listing all sessions

Then open `visualizations/index.html` in your browser.

## Features

### Timeline View
- **Color-coded turns**: Each turn has a unique color for easy visual tracking
- **Tool call entries**: Every tool call is shown with timestamp and duration
- **Interactive**: Click any entry to see full details

### Tool Details Modal
When you click a tool call, you'll see:
- Full arguments passed to the tool
- Complete result/output
- Execution duration
- Timestamp

### Turn Navigation
- Click any turn card to see all tool calls in that turn
- See turn duration and tool count at a glance
- Expandable details for each turn

### Tool Usage Statistics
- **Count**: How many times each tool was used
- **Average Duration**: Mean execution time
- **Total Duration**: Total time spent in each tool
- **Visual bar chart**: Quick comparison of tool usage

### Session Metadata
- Problem description
- Model used
- Success/failure status
- Token usage (input/output)
- Start and completion times

## Data Structure

The visualization reads from session directories that contain:

```
eval_results/test_run/aimeII_2001_p3/20260424-015729/
├── metadata.json          # Session configuration and task
├── final_result.json      # Final status and usage stats
├── tool_timeline.jsonl    # All tool calls (one per line)
├── turn_1.json           # Turn-by-turn data
├── turn_2.json
└── ...
```

## Self-Contained HTML

The generated HTML files are completely self-contained:
- ✅ All data embedded as JSON
- ✅ No external JavaScript libraries
- ✅ No CSS dependencies
- ✅ Works 100% offline
- ✅ Can be shared as a single file

## Browser Compatibility

Works in all modern browsers:
- Chrome/Edge 90+
- Firefox 88+
- Safari 14+

## Examples

### Successful Session
Shows green "SUCCESS" badge, complete tool timeline, and final results.

### Failed Session
Shows red "FAILURE" badge, error details, and partial progress made.

### Long Sessions
Timeline is scrollable, with turn-based navigation for easy jumping between sections.

## Tips

1. **Performance**: Large sessions (50+ turns) may take a moment to render
2. **Sharing**: HTML files can be easily shared via email or file sharing
3. **Comparison**: Open multiple visualizations in separate tabs to compare approaches
4. **Screenshots**: Use browser screenshot tools to capture specific timelines

## Future Enhancements

Potential additions:
- [ ] Side-by-side diff viewer for file changes
- [ ] Search/filter tool calls
- [ ] Export timeline to CSV
- [ ] Compare two sessions side-by-side
- [ ] Zoom/pan timeline for very long sessions
- [ ] Download individual tool outputs

## Troubleshooting

### No data showing
- Check that the session directory contains `metadata.json`
- Verify `tool_timeline.jsonl` exists and has content

### Modal not opening
- Make sure JavaScript is enabled in your browser
- Try a hard refresh (Cmd+Shift+R or Ctrl+Shift+R)

### Styling looks broken
- Open the HTML file via `file://` protocol (not `http://`)
- Check browser console for any errors

## Contributing

To enhance the visualization:
1. Edit `eval/visualize_session.py`
2. The HTML template is embedded in the `generate_html()` function
3. Test with: `python eval/visualize_session.py <test_session> test.html`
4. Check the output in multiple browsers
