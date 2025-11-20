import os
import subprocess
from pathlib import Path
from typing import List, Dict


class ToolRegistry:
    def __init__(self, workspace_root: str | Path | None = None) -> None:
        self.workspace_root = Path(workspace_root) if workspace_root else None

    def _resolve(self, relative_path: str) -> Path:
        if not self.workspace_root:
            raise ValueError("Workspace root not configured for ToolRegistry")
        candidate = (self.workspace_root / relative_path).resolve()
        if not str(candidate).startswith(str(self.workspace_root.resolve())):
            raise ValueError("Path escapes workspace root")
        return candidate

    def list_files(self) -> List[str]:
        root = self.workspace_root or Path(".")
        files = []
        for path in root.rglob("*"):
            if path.is_file():
                files.append(str(path.relative_to(root)))
        return sorted(files)

    def read_file(self, relative_path: str) -> str:
        path = self._resolve(relative_path)
        return path.read_text(encoding="utf-8")

    def write_file(self, relative_path: str, content: str) -> None:
        path = self._resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def run_command(self, command: str) -> Dict[str, str | int]:
        process = subprocess.run(
            command,
            shell=True,
            cwd=str(self.workspace_root) if self.workspace_root else None,
            capture_output=True,
            text=True,
        )
        return {
            "returncode": process.returncode,
            "stdout": process.stdout,
            "stderr": process.stderr,
        }

    def grep_search(self, pattern: str) -> List[Dict[str, str]]:
        root = self.workspace_root or Path(".")
        hits: List[Dict[str, str]] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for idx, line in enumerate(lines, start=1):
                if pattern in line:
                    hits.append({"path": str(path.relative_to(root)), "line": idx, "content": line})
        return hits
