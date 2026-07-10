from __future__ import annotations

import json

from sktr_ai.prompts.advisor_prompt import structured_advisor_context
from sktr_core.plugins import AIReviewContext


def build_summary_prompt(context: AIReviewContext) -> str:
    payload = json.dumps(structured_advisor_context(context), sort_keys=True)
    return f"""You are SKTR's AI Summarizer.

Summarize the structured SKTR analysis concisely. Do not invent files, modules,
dependencies, or issues. Do not infer facts from raw source code.

Structured SKTR context:
{payload}"""
