from __future__ import annotations

from sktr_core.model import FileChange

STATUS_MAP = {
    "A": "added",
    "M": "modified",
    "D": "deleted",
    "R": "renamed",
}


def parse_diff_stats(name_status_output: str, numstat_output: str) -> list[FileChange]:
    changes_by_path = _parse_name_status(name_status_output)
    line_stats = _parse_numstat(numstat_output)

    for path, stats in line_stats.items():
        if path not in changes_by_path:
            changes_by_path[path] = FileChange(path=path, status="modified")
        change = changes_by_path[path]
        changes_by_path[path] = change.model_copy(
            update={
                "added_lines": stats[0],
                "removed_lines": stats[1],
            }
        )

    return list(changes_by_path.values())


def _parse_name_status(output: str) -> dict[str, FileChange]:
    changes: dict[str, FileChange] = {}

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split("\t")
        code = parts[0]
        status_code = code[:1]
        status = STATUS_MAP.get(status_code, "modified")

        if status_code == "R" and len(parts) >= 3:
            old_path = parts[1]
            path = parts[2]
            changes[path] = FileChange(path=path, old_path=old_path, status=status)
        elif len(parts) >= 2:
            path = parts[1]
            changes[path] = FileChange(path=path, status=status)

    return changes


def _parse_numstat(output: str) -> dict[str, tuple[int, int]]:
    stats: dict[str, tuple[int, int]] = {}

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split("\t")
        if len(parts) < 3:
            continue

        added = _parse_line_count(parts[0])
        removed = _parse_line_count(parts[1])
        path = _parse_numstat_path(parts[2])
        stats[path] = (added, removed)

    return stats


def _parse_line_count(value: str) -> int:
    if value == "-":
        return 0
    return int(value)


def _parse_numstat_path(path: str) -> str:
    if " => " not in path:
        return path

    open_brace = path.find("{")
    close_brace = path.find("}", open_brace)
    if open_brace >= 0 and close_brace > open_brace:
        prefix = path[:open_brace]
        inner = path[open_brace + 1 : close_brace]
        suffix = path[close_brace + 1 :]
        if " => " in inner:
            new_name = inner.split(" => ", 1)[1]
            return f"{prefix}{new_name}{suffix}"

    return path.split(" => ", 1)[1]
