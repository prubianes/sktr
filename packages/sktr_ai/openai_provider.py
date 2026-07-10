from __future__ import annotations

import os
import json
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
    "OpenAI provider is configured, but no API key was found. "
    "Set SKTR_OPENAI_API_KEY or OPENAI_API_KEY to enable AI features."
)


@dataclass(frozen=True)
class OpenAIKeyResolution:
    value: str | None
    source: str | None


class OpenAIResponseClient(Protocol):
    def generate(self, *, prompt: str, model: str, api_key: str) -> str: ...


class ResponsesAPIClient:
    """Small standard-library client for the OpenAI Responses API."""

    endpoint = "https://api.openai.com/v1/responses"

    def generate(self, *, prompt: str, model: str, api_key: str) -> str:
        payload = json.dumps({"model": model, "input": prompt}).encode("utf-8")
        request = Request(
            self.endpoint,
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise RuntimeError(f"OpenAI request failed with HTTP {error.code}") from error
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            raise RuntimeError("OpenAI request could not be completed") from error

        output_text = _extract_output_text(body)
        if output_text:
            return output_text
        status = body.get("status")
        suffix = f" (status: {status})" if isinstance(status, str) else ""
        raise RuntimeError(f"OpenAI response did not include output text{suffix}")


def _extract_output_text(body: dict[str, object]) -> str | None:
    """Support both the SDK convenience field and raw Responses API output items."""
    direct_text = body.get("output_text")
    if isinstance(direct_text, str) and direct_text:
        return direct_text

    output = body.get("output")
    if not isinstance(output, list):
        return None

    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for content_part in content:
            if not isinstance(content_part, dict) or content_part.get("type") != "output_text":
                continue
            text = content_part.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts) or None


def resolve_openai_api_key(environ: dict[str, str] | None = None) -> OpenAIKeyResolution:
    """Resolve the SKTR-specific key first, without exposing it to diagnostics."""
    environment = os.environ if environ is None else environ
    for variable in ("SKTR_OPENAI_API_KEY", "OPENAI_API_KEY"):
        value = environment.get(variable)
        if value:
            return OpenAIKeyResolution(value=value, source=variable)
    return OpenAIKeyResolution(value=None, source=None)


class OpenAIProvider:
    """Generate one structured AI Review from deterministic SKTR context."""

    def __init__(
        self,
        *,
        model: str | None = None,
        client: OpenAIResponseClient | None = None,
    ) -> None:
        self.model = model
        self.client = client or ResponsesAPIClient()

    def review(self, context: AIReviewContext) -> AIReview:
        key = resolve_openai_api_key()
        if key.value is None:
            return AIReview(
                provider="openai",
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
                provider="openai",
                model=self._model(),
            )
            review.metadata["api_key_source"] = key.source or "unknown"
            return review
        except RuntimeError as error:
            return AIReview(
                provider="openai",
                model=self.model,
                warnings=[f"OpenAI AI Review unavailable: {error}"],
            )

    def _model(self) -> str:
        return self.model or "gpt-5-mini"


class OpenAIProviderPlugin:
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="openai",
            version=SKTR_VERSION,
            type="ai_provider",
            description="OpenAI AI review provider.",
        )

    def create_ai_provider(self, *, model: str | None = None) -> OpenAIProvider:
        return OpenAIProvider(model=model)
