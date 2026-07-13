from __future__ import annotations

from pathspec import GitIgnoreSpec

from sktr_core.plugins import GitDiff


def filter_git_diff(diff: GitDiff, patterns: list[str]) -> GitDiff:
    if not patterns:
        return diff.model_copy(deep=True)
    spec = GitIgnoreSpec.from_lines(patterns)
    excluded = sorted(path for path in diff.changed_files if spec.match_file(path))
    excluded_set = set(excluded)
    metadata = {
        **diff.metadata,
        "excluded_file_count": str(len(excluded)),
        "excluded_files": ",".join(excluded),
    }
    return diff.model_copy(
        update={
            "changed_files": [path for path in diff.changed_files if path not in excluded_set],
            "file_changes": [change for change in diff.file_changes if change.path not in excluded_set],
            "base_file_contents": {
                path: source for path, source in diff.base_file_contents.items() if path not in excluded_set
            },
            "current_file_contents": {
                path: source for path, source in diff.current_file_contents.items() if path not in excluded_set
            },
            "excluded_files": excluded,
            "repository_files": [
                path for path in diff.repository_files if not spec.match_file(path)
            ],
            "metadata": metadata,
        },
        deep=True,
    )
