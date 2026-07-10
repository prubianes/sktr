from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from sktr_ai import NullAIProvider, OpenAIProvider
from sktr_ai.advisor import parse_advice_response
from sktr_ai.prompts import build_advisor_prompt
from sktr_cli import main as cli_main
from sktr_core.config import load_config
from sktr_core.model import AIAdvice, AIAdviceItem, AIReview, FileChange, Issue, IssueCategory, IssueSeverity, ReviewContext, ReviewResult, System
from sktr_core.pipeline import ReviewPipeline
from sktr_core.plugins import AIReviewContext, GitDiff
from sktr_report import MarkdownOutput, TerminalOutput, review_result_to_artifact

runner = CliRunner()


def test_advice_models_and_review_result_support_advice() -> None:
    advice = AIAdvice(
        provider="openai",
        model="gpt-5-mini",
        items=[AIAdviceItem(title="Review dependency", why="It is new.", suggested_action="Add a boundary.")],
    )

    result = ReviewResult(status="foundation ready", ai_advice=advice)

    assert result.ai_advice is not None
    assert result.ai_advice.items[0].title == "Review dependency"


def test_null_provider_advisor_returns_unavailable_warning() -> None:
    advice = NullAIProvider().advise(AIReviewContext())

    assert advice.items == []
    assert advice.warnings == ["AI Advisor unavailable because no AI provider is configured."]


def test_openai_advisor_missing_key_returns_warning(monkeypatch) -> None:
    monkeypatch.delenv("SKTR_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    advice = OpenAIProvider().advise(AIReviewContext())

    assert advice.provider == "openai"
    assert "no API key was found" in advice.warnings[0]


def test_advisor_prompt_uses_structured_context_without_raw_diff() -> None:
    context = AIReviewContext(
        review=ReviewContext(
            diff_summary="RAW_SOURCE_SHOULD_NOT_APPEAR",
            file_changes=[FileChange(path="src/orders/service.py", status="modified", added_lines=4)],
        ),
        issues=[_issue()],
        system=System(metadata={"knowledge_summary": {"changed_files": 1}}),
    )

    prompt = build_advisor_prompt(context)

    assert "RAW_SOURCE_SHOULD_NOT_APPEAR" not in prompt
    assert "src/orders/service.py" in prompt
    assert "forbidden-dependency" in prompt


def test_openai_advisor_parses_valid_structured_response(monkeypatch) -> None:
    monkeypatch.setenv("SKTR_OPENAI_API_KEY", "test-key")
    client = _FakeClient(
        '{"items":[{"title":"Review Orders to Payments","why":"Cross-module coupling.",'
        '"suggested_action":"Add an application boundary.","related_issue_ids":["forbidden-dependency"],'
        '"related_files":["src/orders/service.py"],"confidence":"medium"}]}'
    )

    advice = OpenAIProvider(model="gpt-5-mini", client=client).advise(_context())

    assert advice.items[0].title == "Review Orders to Payments"
    assert advice.items[0].related_issue_ids == ["forbidden-dependency"]
    assert client.prompts and "RAW_SOURCE_SHOULD_NOT_APPEAR" not in client.prompts[0]


def test_invalid_advisor_response_has_raw_fallback_recommendation() -> None:
    advice = parse_advice_response(response="Extract the payment boundary.", provider="openai", model="gpt-5-mini")

    assert advice.items[0].suggested_action == "Extract the payment boundary."
    assert "parsing failed" in advice.warnings[0]


def test_pipeline_passes_summary_to_advisor() -> None:
    provider = _RecordingProvider()
    result = ReviewPipeline(
        diff=GitDiff(),
        ai_provider=provider,
        run_ai_summary=True,
        run_ai_advice=True,
    ).run()

    assert result.ai_review is not None
    assert result.ai_advice is not None
    assert provider.advisor_context is not None
    assert provider.advisor_context.ai_summary is not None
    assert provider.advisor_context.ai_summary.summary == "Deterministic findings summarized."


def test_ai_feature_config_can_disable_advisor(tmp_path: Path) -> None:
    config_path = tmp_path / "sktr.yml"
    config_path.write_text(
        "ai:\n  enabled: true\n  provider: openai\n  features:\n    summary: true\n    advisor: false\n",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert cli_main._ai_features(config, None) == (True, False)


def test_cli_ai_and_no_ai_select_expected_override(monkeypatch) -> None:
    calls: list[bool | None] = []

    def build(**kwargs) -> ReviewResult:
        calls.append(kwargs["ai_override"])
        return ReviewResult(status="foundation ready")

    monkeypatch.setattr(cli_main, "_build_review_result", build)
    with _isolated(Path.cwd() / ".tmp-ai-cli-test"):
        Path("sktr.yml").write_text("project:\n  name: test\n", encoding="utf-8")
        enabled = runner.invoke(cli_main.app, ["review", "--ai"])
        disabled = runner.invoke(cli_main.app, ["review", "--no-ai"])

    assert enabled.exit_code == 0
    assert disabled.exit_code == 0
    assert calls == [True, False]


def test_outputs_and_artifact_include_cohesive_ai_sections() -> None:
    result = ReviewResult(
        status="foundation ready",
        ai_review=AIReview(summary="Orders gained a new payment dependency."),
        ai_advice=_advice(),
    )

    terminal = TerminalOutput().render(result)
    markdown = MarkdownOutput().render(result)

    assert "AI Summary" in terminal
    assert "[bold]1. Review Orders to Payments[/bold]" in terminal
    assert "Why: The dependency increases coupling." in terminal
    assert "Suggested action: Introduce an application boundary." in terminal
    assert "Related files: src/orders/service.py" in terminal
    assert "## AI Summary" in markdown
    assert "## AI Advisor" in markdown
    assert "**Why:** The dependency increases coupling." in markdown
    assert review_result_to_artifact(result)["ai_advice"]["provider"] == "openai"


def _context() -> AIReviewContext:
    return AIReviewContext(
        review=ReviewContext(
            diff_summary="RAW_SOURCE_SHOULD_NOT_APPEAR",
            file_changes=[FileChange(path="src/orders/service.py", status="modified", added_lines=4)],
        ),
        issues=[_issue()],
        system=System(metadata={"knowledge_summary": {"changed_files": 1}}),
    )


def _issue() -> Issue:
    return Issue(
        id="forbidden-dependency",
        title="Forbidden dependency",
        description="Orders imports Payments directly.",
        severity=IssueSeverity.HIGH,
        category=IssueCategory.ARCHITECTURE,
    )


def _advice() -> AIAdvice:
    return AIAdvice(
        provider="openai",
        model="gpt-5-mini",
        items=[
            AIAdviceItem(
                title="Review Orders to Payments",
                why="The dependency increases coupling.",
                suggested_action="Introduce an application boundary.",
                related_files=["src/orders/service.py"],
            )
        ],
    )


class _FakeClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def generate(self, *, prompt: str, model: str, api_key: str) -> str:
        self.prompts.append(prompt)
        return self.response


class _RecordingProvider:
    def __init__(self) -> None:
        self.advisor_context: AIReviewContext | None = None

    def review(self, context: AIReviewContext) -> AIReview:
        return AIReview(summary="Deterministic findings summarized.")

    def advise(self, context: AIReviewContext) -> AIAdvice:
        self.advisor_context = context
        return _advice()


class _isolated:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.previous = Path.cwd()

    def __enter__(self) -> None:
        import os
        import shutil

        if self.path.exists():
            shutil.rmtree(self.path)
        self.path.mkdir()
        os.chdir(self.path)

    def __exit__(self, exc_type, exc, tb) -> None:
        import os
        import shutil

        os.chdir(self.previous)
        shutil.rmtree(self.path)
