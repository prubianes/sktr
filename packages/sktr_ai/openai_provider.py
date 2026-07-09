from __future__ import annotations

import os
from dataclasses import dataclass

from sktr_core.model import AIReview
from sktr_core.plugins import AIReviewContext, PluginMetadata

MISSING_API_KEY_WARNING = (
    "OpenAI provider is configured, but no API key was found. "
    "Set SKTR_OPENAI_API_KEY or OPENAI_API_KEY to enable AI summaries."
)


@dataclass(frozen=True)
class OpenAIKeyResolution:
    value: str | None
    source: str | None


def resolve_openai_api_key(environ: dict[str, str] | None = None) -> OpenAIKeyResolution:
    """Resolve the SKTR-specific key first, without exposing it to diagnostics."""
    environment = os.environ if environ is None else environ
    for variable in ("SKTR_OPENAI_API_KEY", "OPENAI_API_KEY"):
        value = environment.get(variable)
        if value:
            return OpenAIKeyResolution(value=value, source=variable)
    return OpenAIKeyResolution(value=None, source=None)


class OpenAIProvider:
    """OpenAI integration foundation; model invocation will be added separately."""

    def __init__(self, *, model: str | None = None) -> None:
        self.model = model

    def review(self, context: AIReviewContext) -> AIReview:
        del context
        key = resolve_openai_api_key()
        if key.value is None:
            return AIReview(
                warnings=[MISSING_API_KEY_WARNING],
                model=self.model,
                metadata={"provider": "openai", "api_key_status": "missing"},
            )
        return AIReview(
            model=self.model,
            metadata={"provider": "openai", "api_key_source": key.source or "unknown"},
        )


class OpenAIProviderPlugin:
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="openai",
            version="0.12.0",
            type="ai_provider",
            description="OpenAI AI review provider.",
        )

    def create_ai_provider(self, *, model: str | None = None) -> OpenAIProvider:
        return OpenAIProvider(model=model)
