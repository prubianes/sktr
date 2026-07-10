from __future__ import annotations

import json

from pydantic import ValidationError

from sktr_core.model import AIRecommendation, AIReview


def parse_ai_review_response(*, response: str, provider: str, model: str | None) -> AIReview:
    try:
        payload = json.loads(response)
        overview = payload.get("overview")
        recommendations = payload.get("recommendations")
        if not isinstance(overview, str) or not isinstance(recommendations, list):
            raise ValueError("Response must contain an overview and recommendations list")
        return AIReview(
            provider=provider,
            model=model,
            overview=overview,
            recommendations=[AIRecommendation.model_validate(item) for item in recommendations],
        )
    except (TypeError, ValueError, json.JSONDecodeError, ValidationError) as error:
        return AIReview(
            provider=provider,
            model=model,
            overview=response,
            warnings=[f"Structured AI Review response parsing failed: {error}"],
        )
