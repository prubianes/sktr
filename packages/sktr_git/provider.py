from __future__ import annotations

import subprocess
from pathlib import Path

from sktr_core.plugins import GitDiff
from sktr_git.diff import parse_diff_stats


class SubprocessGitProvider:
    def __init__(self, *, cwd: Path | None = None, base_branch: str = "main") -> None:
        self.cwd = cwd or Path.cwd()
        self.base_branch = base_branch

    def current_diff(self) -> GitDiff:
        repository_root = self.repository_root()
        if repository_root is None:
            return GitDiff()

        raw = self._git(repository_root, "diff", self.base_branch)
        name_status = self._git(repository_root, "diff", "--name-status", "--find-renames", self.base_branch)
        numstat = self._git(repository_root, "diff", "--numstat", "--find-renames", self.base_branch)
        file_changes = parse_diff_stats(name_status, numstat)

        return GitDiff(
            raw=raw,
            repository_root=str(repository_root),
            changed_files=[change.path for change in file_changes],
            file_changes=file_changes,
        )

    def changed_files(self) -> list[str]:
        return self.current_diff().changed_files

    def repository_root(self) -> Path | None:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=self.cwd,
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode != 0:
            return None
        return Path(result.stdout.strip())

    def _git(self, repository_root: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=repository_root,
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode != 0:
            return ""
        return result.stdout
