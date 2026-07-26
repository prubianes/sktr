from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sktr_ai.prompts import build_ai_review_prompt
from sktr_ai.review import parse_ai_review_response
from sktr_core.model import AIReview
from sktr_core.plugins import AIReviewContext, PluginMetadata
from sktr_core.version import SKTR_VERSION

MISSING_API_KEY_WARNING = (
    "Anthropic provider is configured, but no API key was found. "
    "Set SKTR_ANTHROPIC_API_KEY or ANTHROPIC_API_KEY to enable AI features."
)
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"
ANTHROPIC_MODEL_PROFILES = [
    ("Balanced - Claude Sonnet 5 (recommended)", "claude-sonnet-5"),
    ("Fast - Claude Haiku 4.5", "claude-haiku-4-5"),
    ("Best quality - Claude Opus 5", "claude-opus-5"),
]


@dataclass(frozen=True)
class AnthropicKeyResolution:
    value: str | None
    source: str | None


class AnthropicResponseClient(Protocol):
    def generate(self, *, prompt: str, model: str, api_key: str) -> str: ...


class MessagesAPIClient:
    """Small standard-library client for Anthropic's Messages API."""

    endpoint = "https://api.anthropic.com/v1/messages"

    def generate(self, *, prompt: str, model: str, api_key: str) -> str:
        payload = json.dumps(
            {
                "model": model,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
            }
        ).encode("utf-8")
        request = Request(
            self.endpoint,
            data=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise RuntimeError(f"Anthropic request failed with HTTP {error.code}") from error
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            raise RuntimeError("Anthropic request could not be completed") from error

        output_text = _extract_message_text(body)
        if output_text:
            return output_text
        stop_reason = body.get("stop_reason")
        suffix = f" (stop reason: {stop_reason})" if isinstance(stop_reason, str) else ""
        raise RuntimeError(f"Anthropic response did not include output text{suffix}")


def _extract_message_text(body: dict[str, object]) -> str | None:
    content = body.get("content")
    if not isinstance(content, list):
        return None
    parts = [
        part["text"]
        for part in content
        if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str)
    ]
    return "".join(parts) or None


def resolve_anthropic_api_key(environ: dict[str, str] | None = None) -> AnthropicKeyResolution:
    """Resolve the SKTR-specific key first, without exposing it to diagnostics."""
    environment = os.environ if environ is None else environ
    for variable in ("SKTR_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"):
        value = environment.get(variable)
        if value:
            return AnthropicKeyResolution(value=value, source=variable)
    return AnthropicKeyResolution(value=None, source=None)


class AnthropicProvider:
    """Generate one structured AI Review from deterministic SKTR context."""

    def __init__(
        self,
        *,
        model: str | None = None,
        client: AnthropicResponseClient | None = None,
    ) -> None:
        self.model = model
        self.client = client or MessagesAPIClient()

    def review(self, context: AIReviewContext) -> AIReview:
        key = resolve_anthropic_api_key()
        if key.value is None:
            return AIReview(
                provider="anthropic",
                warnings=[MISSING_API_KEY_WARNING],
                model=self.model,
                metadata={"api_key_status": "missing"},
            )
        try:
            response = self.client.generate(
                prompt=build_ai_review_prompt(context),
                model=self._model(),
                api_key=key.value,
            )
            review = parse_ai_review_response(
                response=response,
                provider="anthropic",
                model=self._model(),
            )
            review.metadata["api_key_source"] = key.source or "unknown"
            return review
        except RuntimeError as error:
            return AIReview(
                provider="anthropic",
                model=self.model,
                warnings=[f"Anthropic AI Review unavailable: {error}"],
            )

    def _model(self) -> str:
        return self.model or DEFAULT_ANTHROPIC_MODEL


class AnthropicProviderPlugin:
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="anthropic",
            version=SKTR_VERSION,
            type="ai_provider",
            description="Anthropic Claude AI review provider.",
        )

    def create_ai_provider(self, *, model: str | None = None) -> AnthropicProvider:
        return AnthropicProvider(model=model)
