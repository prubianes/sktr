from __future__ import annotations

from sktr_core.model import AIReview
from sktr_core.plugins import AIReviewContext


class NullAIProvider:
    """Safe provider used when AI was explicitly requested without configuration."""

    def review(self, context: AIReviewContext) -> AIReview:
        del context
        return AIReview(
            provider="none",
            warnings=["AI Review unavailable because no AI provider is configured."],
        )
