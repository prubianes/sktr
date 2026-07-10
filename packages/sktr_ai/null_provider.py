from __future__ import annotations

from sktr_core.model import AIAdvice, AIReview
from sktr_core.plugins import AIReviewContext


class NullAIProvider:
    """Safe provider used when AI was explicitly requested without configuration."""

    def review(self, context: AIReviewContext) -> AIReview:
        del context
        return AIReview(warnings=["AI Summary unavailable because no AI provider is configured."])

    def advise(self, context: AIReviewContext) -> AIAdvice:
        del context
        return AIAdvice(
            provider="none",
            warnings=["AI Advisor unavailable because no AI provider is configured."],
        )
