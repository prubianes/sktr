from __future__ import annotations

import json

from sktr_core.model import AIAdvice, AIAdviceItem


def parse_advice_response(*, response: str, provider: str, model: str | None) -> AIAdvice:
    """Parse the provider's structured answer while preserving a useful fallback."""
    try:
        payload = json.loads(response)
        items = payload.get("items")
        if not isinstance(items, list):
            raise ValueError("Response does not contain an items list")
        return AIAdvice(provider=provider, model=model, items=[AIAdviceItem.model_validate(item) for item in items])
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        return AIAdvice(
            provider=provider,
            model=model,
            items=[
                AIAdviceItem(
                    title="AI advisor response",
                    why="The provider returned an unstructured recommendation.",
                    suggested_action=response,
                )
            ],
            warnings=[f"Structured AI advisor response parsing failed: {error}"],
        )
