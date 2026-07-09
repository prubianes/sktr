from __future__ import annotations

from pathlib import Path
import subprocess

from sktr_git import ReviewScope, SubprocessGitProvider


class FakeGitRunner:
    def __init__(self, outputs: dict[tuple[str, ...], str] | None = None) -> None:
        self.outputs = outputs or {}
        self.calls: list[list[str]] = []

    def __call__(
        self,
        args: list[str],
        *,
        cwd: Path,
        capture_output: bool,
        check: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        output = self.outputs.get(tuple(args), "")
        if args == ["git", "rev-parse", "--show-toplevel"]:
            output = "/repo\n"
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=output, stderr="")


def test_working_tree_review_diffs_against_head() -> None:
    runner = FakeGitRunner(
        {
            ("git", "diff", "--name-status", "--find-renames", "HEAD"): "M\tapp.py\n",
            ("git", "diff", "--numstat", "--find-renames", "HEAD"): "3\t1\tapp.py\n",
        }
    )

    diff = SubprocessGitProvider(runner=runner).current_diff()

    assert diff.metadata["review_scope"] == "working_tree"
    assert diff.metadata["diff_target"] == "HEAD"
    assert diff.changed_files == ["app.py"]
    assert ["git", "diff", "HEAD"] in runner.calls


def test_branch_review_uses_merge_base_with_default_base_branch() -> None:
    runner = FakeGitRunner(
        {
            ("git", "merge-base", "main", "HEAD"): "abc123\n",
            ("git", "diff", "--name-status", "--find-renames", "abc123", "HEAD"): "A\tfeature.py\n",
            ("git", "diff", "--numstat", "--find-renames", "abc123", "HEAD"): "10\t0\tfeature.py\n",
        }
    )

    diff = SubprocessGitProvider(scope=ReviewScope.BRANCH, runner=runner).current_diff()

    assert diff.metadata["review_scope"] == "branch"
    assert diff.metadata["base_branch"] == "main"
    assert diff.metadata["diff_target"] == "abc123 HEAD"
    assert ["git", "merge-base", "main", "HEAD"] in runner.calls
    assert ["git", "diff", "abc123", "HEAD"] in runner.calls


def test_branch_review_supports_explicit_base_branch() -> None:
    runner = FakeGitRunner(
        {
            ("git", "merge-base", "develop", "HEAD"): "def456\n",
        }
    )

    diff = SubprocessGitProvider(
        scope=ReviewScope.BRANCH,
        base_branch="develop",
        runner=runner,
    ).current_diff()

    assert diff.metadata["base_branch"] == "develop"
    assert diff.metadata["diff_target"] == "def456 HEAD"
    assert ["git", "merge-base", "develop", "HEAD"] in runner.calls


def test_commit_review_diffs_commit_against_parent() -> None:
    runner = FakeGitRunner(
        {
            ("git", "diff", "--name-status", "--find-renames", "HEAD~1^", "HEAD~1"): "D\told.py\n",
            ("git", "diff", "--numstat", "--find-renames", "HEAD~1^", "HEAD~1"): "0\t8\told.py\n",
        }
    )

    diff = SubprocessGitProvider(
        scope=ReviewScope.COMMIT,
        commit="HEAD~1",
        runner=runner,
    ).current_diff()

    assert diff.metadata["review_scope"] == "commit"
    assert diff.metadata["diff_target"] == "HEAD~1^ HEAD~1"
    assert diff.changed_files == ["old.py"]
    assert ["git", "diff", "HEAD~1^", "HEAD~1"] in runner.calls
