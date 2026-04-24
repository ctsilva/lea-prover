"""Fast Lean checking using leanclient library and persistent LSP server."""

import threading
from pathlib import Path
from typing import Optional
import atexit

try:
    from leanclient import LeanLSPClient
    LEANCLIENT_AVAILABLE = True
except ImportError:
    LEANCLIENT_AVAILABLE = False


class LeanLSPManager:
    """Manages a persistent Lean LSP server using leanclient."""

    def __init__(self):
        self.clients = {}  # lake_root -> LeanClient
        self.lock = threading.Lock()

        # Register cleanup on exit
        atexit.register(self.shutdown_all)

    def _find_lake_root(self, path: str) -> Optional[str]:
        """Walk up from path looking for lakefile.lean or lakefile.toml."""
        p = Path(path).resolve()
        for parent in [p.parent, *p.parent.parents]:
            if (parent / "lakefile.lean").exists() or (parent / "lakefile.toml").exists():
                return str(parent)
        return None

    def _get_client(self, lake_root: str) -> 'LeanLSPClient':
        """Get or create a Lean client for the given lake root."""
        if lake_root in self.clients:
            return self.clients[lake_root]

        # Create new client
        client = LeanLSPClient(lake_root)
        self.clients[lake_root] = client
        return client

    def check_file(self, file_path: str, timeout: float = 120.0) -> str:
        """Check a Lean file using persistent LSP server via leanclient.

        Args:
            file_path: Absolute path to the .lean file
            timeout: Maximum time to wait for checking (seconds)

        Returns:
            String with diagnostics or "OK" if no errors
        """
        if not LEANCLIENT_AVAILABLE:
            # Fall back to direct checking if leanclient not available
            return self._fallback_check(file_path, timeout)

        with self.lock:
            path = Path(file_path).resolve()
            if not path.exists():
                return f"Error: {path} does not exist."

            # Find lake root
            lake_root = self._find_lake_root(str(path))
            if not lake_root:
                # Fall back to standalone lean
                return self._fallback_check(str(path), timeout)

            try:
                client = self._get_client(lake_root)

                # leanclient expects paths relative to project root
                rel_path = str(path.relative_to(lake_root))

                # Open the file first (required by leanclient)
                client.open_file(rel_path)

                # Get diagnostics using leanclient API
                diag_result = client.get_diagnostics(rel_path, inactivity_timeout=timeout)

                # Close the file to clean up
                client.close_files([rel_path])

                if not diag_result.diagnostics:
                    return "OK — no errors, no warnings."

                # Format diagnostics into readable output
                result_lines = []
                for diag in diag_result.diagnostics:
                    # Diagnostics format from leanclient LSP response
                    severity = diag.get('severity', 1)
                    severity_str = {1: "error", 2: "warning", 3: "info", 4: "hint"}.get(severity, "error")
                    message = diag.get('message', '')
                    range_info = diag.get('range', {})
                    start = range_info.get('start', {})
                    line = start.get('line', 0) + 1  # LSP is 0-indexed
                    col = start.get('character', 0) + 1

                    result_lines.append(f"{path.name}:{line}:{col}: {severity_str}: {message}")

                return "\n".join(result_lines)

            except Exception as e:
                # Client failed, fall back to direct checking
                print(f"  [leanclient failed: {e}, falling back...]", flush=True)
                if lake_root in self.clients:
                    try:
                        self.clients[lake_root].close()
                    except:
                        pass
                    del self.clients[lake_root]
                return self._fallback_check(str(path), timeout)

    def _fallback_check(self, path: str, timeout: float = 120.0) -> str:
        """Fallback to direct lean command."""
        import subprocess

        p = Path(path).resolve()
        lake_root = self._find_lake_root(str(p))

        if lake_root:
            cmd = ["lake", "env", "lean", str(p)]
            cwd = lake_root
        else:
            cmd = ["lean", str(p)]
            cwd = str(p.parent)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd
            )
            output = (result.stdout + "\n" + result.stderr).strip()
            if result.returncode == 0 and not output:
                return "OK — no errors, no warnings."
            return output if output else f"Exit code {result.returncode} (no output)."
        except subprocess.TimeoutExpired:
            return f"Error: lean timed out after {timeout}s."
        except FileNotFoundError:
            return "Error: `lean` or `lake` not found. Is Lean 4 installed?"

    def shutdown_all(self):
        """Shutdown all LSP client connections."""
        with self.lock:
            for client in self.clients.values():
                try:
                    client.close()
                except:
                    pass
            self.clients.clear()


# Global singleton instance
_global_lsp_manager: Optional[LeanLSPManager] = None


def get_lsp_manager() -> LeanLSPManager:
    """Get or create the global LSP manager singleton."""
    global _global_lsp_manager
    if _global_lsp_manager is None:
        _global_lsp_manager = LeanLSPManager()
    return _global_lsp_manager
