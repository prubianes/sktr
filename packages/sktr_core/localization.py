from __future__ import annotations

import re

DEFAULT_LANGUAGE = "en"
SUPPORTED_OUTPUT_LANGUAGES = ("en", "es")
_LANGUAGE_TAG = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


def normalize_language_tag(value: str) -> str:
    """Normalize and validate a practical BCP 47 language tag."""
    normalized = value.strip().replace("_", "-")
    if not _LANGUAGE_TAG.fullmatch(normalized):
        raise ValueError(
            "language must be a BCP 47 tag such as en, es, pt-BR, or ja"
        )
    parts = normalized.split("-")
    normalized_parts = [parts[0].lower()]
    for part in parts[1:]:
        if len(part) == 2 and part.isalpha():
            normalized_parts.append(part.upper())
        elif len(part) == 4 and part.isalpha():
            normalized_parts.append(part.title())
        else:
            normalized_parts.append(part.lower())
    return "-".join(normalized_parts)


def deterministic_language(requested: str) -> str:
    """Return the supported catalog language, falling back to English."""
    normalized = normalize_language_tag(requested)
    primary = normalized.split("-", 1)[0]
    return primary if primary in SUPPORTED_OUTPUT_LANGUAGES else DEFAULT_LANGUAGE


def is_output_language_supported(requested: str) -> bool:
    return deterministic_language(requested) != DEFAULT_LANGUAGE or requested.split("-", 1)[0].lower() == "en"
