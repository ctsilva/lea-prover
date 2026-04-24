"""File snapshot system for tracking proof evolution.

This module captures snapshots of .lean files at different stages:
- Before: Initial state before agent starts
- Intermediate: After each file modification (per turn)
- After: Final state when agent completes

This allows us to:
- See proof evolution across turns
- Reproduce any intermediate state
- Debug what was actually checked at each turn
- Benchmark performance on actual intermediate files
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


class SnapshotManager:
    """Manages file snapshots for a session."""

    def __init__(self, result_dir: Path | None, session_id: str, workspace_dir: Path):
        """Initialize snapshot manager.

        Args:
            result_dir: Base directory for results
            session_id: Unique session identifier
            workspace_dir: Path to workspace directory containing .lean files
        """
        self.result_dir = result_dir
        self.session_id = session_id
        self.workspace_dir = Path(workspace_dir)
        self.snapshot_base = None

        if result_dir:
            self.snapshot_base = Path(result_dir) / session_id / "snapshots"
            self.snapshot_base.mkdir(parents=True, exist_ok=True)

    def capture_before_snapshot(self) -> dict:
        """Capture initial state of all .lean files in workspace.

        Returns:
            Manifest dict with file metadata
        """
        if not self.snapshot_base:
            return {}

        before_dir = self.snapshot_base / "before"
        before_dir.mkdir(exist_ok=True)

        manifest = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "before",
            "files": []
        }

        # Find all .lean files in workspace
        lean_files = list(self.workspace_dir.rglob("*.lean"))

        for lean_file in lean_files:
            if not lean_file.exists() or not lean_file.is_file():
                continue

            # Calculate relative path from workspace
            try:
                rel_path = lean_file.relative_to(self.workspace_dir)
            except ValueError:
                # File is outside workspace, skip
                continue

            # Create destination path preserving directory structure
            dest_path = before_dir / rel_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(lean_file, dest_path)

            # Track metadata
            content = lean_file.read_text()
            lines = len(content.splitlines())
            sorries = content.count("sorry")

            manifest["files"].append({
                "path": str(rel_path),
                "absolute_path": str(lean_file),
                "lines": lines,
                "sorries": sorries,
                "size_bytes": lean_file.stat().st_size
            })

        # Save manifest
        manifest_file = before_dir / "manifest.json"
        manifest_file.write_text(json.dumps(manifest, indent=2))

        return manifest

    def capture_intermediate_snapshot(self, turn: int, modified_files: list[str]):
        """Capture snapshot of specific files after a turn modification.

        Args:
            turn: Current turn number
            modified_files: List of absolute paths to files that were modified
        """
        if not self.snapshot_base or not modified_files:
            return

        turn_dir = self.snapshot_base / f"turn_{turn}"
        turn_dir.mkdir(exist_ok=True)

        snapshot_info = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "turn": turn,
            "type": "intermediate",
            "files": []
        }

        for file_path in modified_files:
            file_path = Path(file_path)
            if not file_path.exists() or not file_path.is_file():
                continue

            # Skip non-.lean files
            if file_path.suffix != ".lean":
                continue

            # Calculate relative path if possible
            try:
                rel_path = file_path.relative_to(self.workspace_dir)
            except ValueError:
                # File is outside workspace, use filename only
                rel_path = Path(file_path.name)

            # Create destination path
            dest_path = turn_dir / rel_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(file_path, dest_path)

            # Track metadata
            content = file_path.read_text()
            lines = len(content.splitlines())
            sorries = content.count("sorry")

            snapshot_info["files"].append({
                "path": str(rel_path),
                "absolute_path": str(file_path),
                "lines": lines,
                "sorries": sorries,
                "size_bytes": file_path.stat().st_size
            })

        # Save snapshot info
        info_file = turn_dir / "snapshot_info.json"
        info_file.write_text(json.dumps(snapshot_info, indent=2))

    def capture_after_snapshot(self) -> dict:
        """Capture final state of all .lean files and compute diff.

        Returns:
            Summary dict with before/after comparison
        """
        if not self.snapshot_base:
            return {}

        after_dir = self.snapshot_base / "after"
        after_dir.mkdir(exist_ok=True)

        manifest = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "after",
            "files": []
        }

        # Find all .lean files in workspace
        lean_files = list(self.workspace_dir.rglob("*.lean"))

        for lean_file in lean_files:
            if not lean_file.exists() or not lean_file.is_file():
                continue

            # Calculate relative path from workspace
            try:
                rel_path = lean_file.relative_to(self.workspace_dir)
            except ValueError:
                continue

            # Create destination path
            dest_path = after_dir / rel_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(lean_file, dest_path)

            # Track metadata
            content = lean_file.read_text()
            lines = len(content.splitlines())
            sorries = content.count("sorry")

            manifest["files"].append({
                "path": str(rel_path),
                "absolute_path": str(lean_file),
                "lines": lines,
                "sorries": sorries,
                "size_bytes": lean_file.stat().st_size
            })

        # Save manifest
        manifest_file = after_dir / "manifest.json"
        manifest_file.write_text(json.dumps(manifest, indent=2))

        # Compute diff with before snapshot
        diff_summary = self._compute_diff()

        # Save diff summary
        diff_file = self.snapshot_base / "diff_summary.json"
        diff_file.write_text(json.dumps(diff_summary, indent=2))

        return diff_summary

    def _compute_diff(self) -> dict:
        """Compute diff between before and after snapshots.

        Returns:
            Dict with added, modified, deleted files and metric changes
        """
        before_dir = self.snapshot_base / "before"
        after_dir = self.snapshot_base / "after"

        # Load manifests
        before_manifest = {}
        after_manifest = {}

        before_manifest_file = before_dir / "manifest.json"
        after_manifest_file = after_dir / "manifest.json"

        if before_manifest_file.exists():
            before_manifest = json.loads(before_manifest_file.read_text())

        if after_manifest_file.exists():
            after_manifest = json.loads(after_manifest_file.read_text())

        # Build file maps
        before_files = {f["path"]: f for f in before_manifest.get("files", [])}
        after_files = {f["path"]: f for f in after_manifest.get("files", [])}

        # Compute changes
        added = []
        modified = []
        deleted = []
        unchanged = []

        for path in after_files:
            if path not in before_files:
                added.append(path)
            elif (after_files[path]["lines"] != before_files[path]["lines"] or
                  after_files[path]["sorries"] != before_files[path]["sorries"]):
                modified.append({
                    "path": path,
                    "before": {
                        "lines": before_files[path]["lines"],
                        "sorries": before_files[path]["sorries"]
                    },
                    "after": {
                        "lines": after_files[path]["lines"],
                        "sorries": after_files[path]["sorries"]
                    },
                    "delta": {
                        "lines": after_files[path]["lines"] - before_files[path]["lines"],
                        "sorries": after_files[path]["sorries"] - before_files[path]["sorries"]
                    }
                })
            else:
                unchanged.append(path)

        for path in before_files:
            if path not in after_files:
                deleted.append(path)

        # Aggregate metrics
        total_lines_before = sum(f["lines"] for f in before_files.values())
        total_lines_after = sum(f["lines"] for f in after_files.values())
        total_sorries_before = sum(f["sorries"] for f in before_files.values())
        total_sorries_after = sum(f["sorries"] for f in after_files.values())

        return {
            "summary": {
                "files_added": len(added),
                "files_modified": len(modified),
                "files_deleted": len(deleted),
                "files_unchanged": len(unchanged),
                "total_lines_delta": total_lines_after - total_lines_before,
                "total_sorries_delta": total_sorries_after - total_sorries_before
            },
            "added": added,
            "modified": modified,
            "deleted": deleted,
            "unchanged": unchanged,
            "metrics": {
                "before": {
                    "total_lines": total_lines_before,
                    "total_sorries": total_sorries_before,
                    "file_count": len(before_files)
                },
                "after": {
                    "total_lines": total_lines_after,
                    "total_sorries": total_sorries_after,
                    "file_count": len(after_files)
                }
            }
        }

    def restore_from_snapshot(self, snapshot_type: str = "before"):
        """Restore workspace files from a snapshot.

        Args:
            snapshot_type: "before", "after", or "turn_N" where N is turn number
        """
        if not self.snapshot_base:
            raise ValueError("No snapshot base directory configured")

        snapshot_dir = self.snapshot_base / snapshot_type
        if not snapshot_dir.exists():
            raise ValueError(f"Snapshot directory not found: {snapshot_dir}")

        # Find all .lean files in snapshot
        for snapshot_file in snapshot_dir.rglob("*.lean"):
            # Calculate relative path from snapshot dir
            rel_path = snapshot_file.relative_to(snapshot_dir)

            # Determine destination in workspace
            dest_file = self.workspace_dir / rel_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            # Restore file
            shutil.copy2(snapshot_file, dest_file)
            print(f"Restored: {rel_path}")

        print(f"Workspace restored from snapshot: {snapshot_type}")
