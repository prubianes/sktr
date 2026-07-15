from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from sktr_git import GitProviderError, ReviewScope, SubprocessGitProvider


class FakeGitRunner:
    def __init__(
        self,
        outputs: dict[tuple[str, ...], str] | None = None,
        *,
        root: Path | None = None,
    ) -> None:
        self.outputs = outputs or {}
        self.root = root or Path("/repo")
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
            output = f"{self.root}\n"
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=output, stderr="")


class FailingGitRunner(FakeGitRunner):
    def __init__(self, failing_command: tuple[str, ...], stderr: str) -> None:
        super().__init__()
        self.failing_command = failing_command
        self.stderr = stderr

    def __call__(self, args: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        if tuple(args) == self.failing_command:
            return subprocess.CompletedProcess(args=args, returncode=128, stdout="", stderr=self.stderr)
        return super().__call__(args, **kwargs)


def test_working_tree_review_diffs_against_head() -> None:
    runner = FakeGitRunner(
        {
            ("git", "diff", "--name-status", "--find-renames", "HEAD"): "M\tapp.py\n",
            ("git", "diff", "--numstat", "--find-renames", "HEAD"): "3\t1\tapp.py\n",
            ("git", "show", "HEAD:app.py"): "import os\n",
        }
    )

    diff = SubprocessGitProvider(runner=runner).current_diff()

    assert diff.metadata["review_scope"] == "working_tree"
    assert diff.metadata["diff_target"] == "HEAD"
    assert diff.changed_files == ["app.py"]
    assert diff.base_file_contents == {"app.py": "import os\n"}
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


def test_repository_snapshot_reads_git_managed_text_files(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src/app.py").write_text("import service\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# App\n", encoding="utf-8")
    runner = FakeGitRunner(
        {
            (
                "git",
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
            ): "src/app.py\nREADME.md\nmissing.txt\n",
        },
        root=tmp_path,
    )

    snapshot = SubprocessGitProvider(runner=runner).repository_snapshot()

    assert snapshot.changed_files == ["README.md", "src/app.py"]
    assert snapshot.current_file_contents["src/app.py"] == "import service\n"
    assert all(change.status == "unchanged" for change in snapshot.file_changes)
    assert snapshot.metadata["graph_scope"] == "repository"


def test_repository_snapshot_can_read_a_historical_revision(tmp_path: Path) -> None:
    runner = FakeGitRunner(
        {
            ("git", "ls-tree", "-r", "--name-only", "abc123"): "src/app.py\n",
            ("git", "show", "abc123:src/app.py"): "from historical import service\n",
        },
        root=tmp_path,
    )

    snapshot = SubprocessGitProvider(runner=runner).repository_snapshot(revision="abc123")

    assert snapshot.current_file_contents == {"src/app.py": "from historical import service\n"}
    assert snapshot.metadata["repository_revision"] == "abc123"


def test_invalid_base_branch_raises_typed_error() -> None:
    runner = FailingGitRunner(
        ("git", "merge-base", "missing", "HEAD"),
        "fatal: Not a valid object name missing\n",
    )

    with pytest.raises(GitProviderError, match="resolve merge base failed") as raised:
        SubprocessGitProvider(
            scope=ReviewScope.BRANCH,
            base_branch="missing",
            runner=runner,
        ).current_diff()

    assert raised.value.operation == "resolve merge base"
    assert raised.value.message == "fatal: Not a valid object name missing"


def test_invalid_commit_raises_instead_of_returning_empty_review() -> None:
    command = ("git", "diff", "missing^", "missing")
    runner = FailingGitRunner(command, "fatal: ambiguous argument 'missing^'")

    with pytest.raises(GitProviderError, match="read Git diff failed"):
        SubprocessGitProvider(
            scope=ReviewScope.COMMIT,
            commit="missing",
            runner=runner,
        ).current_diff()


def test_missing_optional_file_at_revision_does_not_fail_review() -> None:
    runner = FailingGitRunner(
        ("git", "show", "HEAD:app.py"),
        "fatal: path 'app.py' does not exist in 'HEAD'",
    )
    runner.outputs[("git", "diff", "--name-status", "--find-renames", "HEAD")] = "M\tapp.py\n"
    runner.outputs[("git", "diff", "--numstat", "--find-renames", "HEAD")] = "1\t1\tapp.py\n"

    diff = SubprocessGitProvider(runner=runner).current_diff()

    assert diff.changed_files == ["app.py"]
    assert diff.base_file_contents == {}


def test_git_errors_redact_url_credentials() -> None:
    runner = FailingGitRunner(
        ("git", "diff", "HEAD"),
        "fatal: unable to access 'https://secret-user:secret-token@example.test/repo.git/'",
    )

    with pytest.raises(GitProviderError) as raised:
        SubprocessGitProvider(runner=runner).current_diff()

    assert "secret-user" not in str(raised.value)
    assert "secret-token" not in str(raised.value)
    assert "https://***@example.test/repo.git/" in str(raised.value)


def test_repository_without_head_fails_instead_of_returning_empty_review() -> None:
    runner = FailingGitRunner(
        ("git", "diff", "HEAD"),
        "fatal: ambiguous argument 'HEAD': unknown revision",
    )

    with pytest.raises(GitProviderError, match="read Git diff failed"):
        SubprocessGitProvider(runner=runner).current_diff()


def test_historical_repository_snapshot_failure_is_not_silenced() -> None:
    runner = FailingGitRunner(
        ("git", "ls-tree", "-r", "--name-only", "missing"),
        "fatal: Not a valid object name missing",
    )

    with pytest.raises(GitProviderError, match="list repository files failed"):
        SubprocessGitProvider(runner=runner).repository_snapshot(revision="missing")
