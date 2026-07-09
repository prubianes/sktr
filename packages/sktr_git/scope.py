from __future__ import annotations

from enum import StrEnum


class ReviewScope(StrEnum):
    WORKING_TREE = "working_tree"
    COMMIT = "commit"
    BRANCH = "branch"
    RANGE = "range"
