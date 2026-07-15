from __future__ import annotations

import re


_URL_CREDENTIALS = re.compile(r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*://)[^\s/@]+(?::[^\s/@]*)?@")


class GitProviderError(RuntimeError):
    """A required Git operation failed while resolving review input."""

    def __init__(self, operation: str, message: str) -> None:
        self.operation = operation
        self.message = _sanitize(message)
        super().__init__(f"{operation} failed: {self.message}")


def _sanitize(message: str) -> str:
    compact = " ".join(message.strip().split())
    compact = _URL_CREDENTIALS.sub(r"\g<scheme>***@", compact)
    return compact or "Git did not provide an error message"
