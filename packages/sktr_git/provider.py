from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Protocol

from sktr_core.plugins import GitDiff
from sktr_git.diff import parse_diff_stats
from sktr_git.scope import ReviewScope


class GitCommandRunner(Protocol):
    def __call__(
        self,
        args: list[str],
        *,
        cwd: Path,
        capture_output: bool,
        check: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]: ...


class SubprocessGitProvider:
    def __init__(
        self,
        *,
        cwd: Path | None = None,
        scope: ReviewScope = ReviewScope.WORKING_TREE,
        base_branch: str = "main",
        commit: str | None = None,
        range_spec: str | None = None,
        runner: GitCommandRunner = subprocess.run,
    ) -> None:
        self.cwd = cwd or Path.cwd()
        self.scope = scope
        self.base_branch = base_branch
        self.commit = commit
        self.range_spec = range_spec
        self.runner = runner

    def current_diff(self) -> GitDiff:
        repository_root = self.repository_root()
        if repository_root is None:
            return GitDiff()

        diff_target = self._diff_target(repository_root)
        raw = self._git(repository_root, "diff", *diff_target)
        name_status = self._git(repository_root, "diff", "--name-status", "--find-renames", *diff_target)
        numstat = self._git(repository_root, "diff", "--numstat", "--find-renames", *diff_target)
        file_changes = parse_diff_stats(name_status, numstat)

        return GitDiff(
            raw=raw,
            repository_root=str(repository_root),
            changed_files=[change.path for change in file_changes],
            file_changes=file_changes,
            metadata={
                "review_scope": self.scope.value,
                "base_branch": self.base_branch,
                "diff_target": " ".join(diff_target),
            },
        )

    def changed_files(self) -> list[str]:
        return self.current_diff().changed_files

    def repository_root(self) -> Path | None:
        result = self.runner(
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
        result = self.runner(
            ["git", *args],
            cwd=repository_root,
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode != 0:
            return ""
        return result.stdout

    def _diff_target(self, repository_root: Path) -> list[str]:
        if self.scope == ReviewScope.WORKING_TREE:
            return ["HEAD"]

        if self.scope == ReviewScope.BRANCH:
            merge_base = self._git(repository_root, "merge-base", self.base_branch, "HEAD").strip()
            if not merge_base:
                return [self.base_branch, "HEAD"]
            return [merge_base, "HEAD"]

        if self.scope == ReviewScope.COMMIT:
            if self.commit is None:
                raise ValueError("commit is required for commit review scope")
            return [f"{self.commit}^", self.commit]

        if self.scope == ReviewScope.RANGE:
            if self.range_spec is None:
                raise ValueError("range_spec is required for range review scope")
            return [self.range_spec]

        raise ValueError(f"Unsupported review scope: {self.scope}")
