from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError
from typer.testing import CliRunner

from sktr_ai import NullAIProvider, OpenAIProvider
from sktr_ai.prompts import build_ai_review_prompt, structured_review_context
from sktr_ai.review import parse_ai_review_response
from sktr_cli import main as cli_main
from sktr_core.config import load_config
from sktr_core.model import (
    AIRecommendation,
    AIReview,
    FileChange,
    Issue,
    IssueCategory,
    IssueSeverity,
    ReviewContext,
    ReviewResult,
    System,
)
from sktr_core.pipeline import ReviewPipeline
from sktr_core.plugins import AIReviewContext, GitDiff
from sktr_report import MarkdownOutput, TerminalOutput, review_result_to_artifact

runner = CliRunner()


def test_ai_review_model_contains_overview_and_recommendations() -> None:
    review = _ai_review()
    result = ReviewResult(status="foundation ready", ai_review=review)

    assert result.ai_review is not None
    assert result.ai_review.overview == "Orders gained a payment dependency."
    assert result.ai_review.recommendations[0].title == "Review Orders to Payments"


def test_null_provider_returns_unavailable_review() -> None:
    review = NullAIProvider().review(AIReviewContext())

    assert review.provider == "none"
    assert review.recommendations == []
    assert review.warnings == ["AI Review unavailable because no AI provider is configured."]


def test_openai_missing_key_returns_warning(monkeypatch) -> None:
    monkeypatch.delenv("SKTR_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    review = OpenAIProvider().review(AIReviewContext())

    assert review.provider == "openai"
    assert "no API key was found" in review.warnings[0]


def test_ai_review_prompt_uses_structured_context_without_raw_diff() -> None:
    prompt = build_ai_review_prompt(_context())

    assert "RAW_SOURCE_SHOULD_NOT_APPEAR" not in prompt
    assert "src/orders/service.py" in prompt
    assert "forbidden-dependency" in prompt


def test_ai_context_aggregates_repeated_findings() -> None:
    context = _context()
    template = context.issues[0]
    context.issues = [template.model_copy(update={"id": f"forbidden-{index}"}) for index in range(50)]

    payload = structured_review_context(context)

    assert payload["issue_groups"][0]["count"] == 50
    assert len(payload["priority_issues"]) == 20
    assert payload["context_limits"]["issues_total"] == 50


def test_openai_parses_unified_review_in_one_call(monkeypatch) -> None:
    monkeypatch.setenv("SKTR_OPENAI_API_KEY", "test-key")
    client = _FakeClient(
        '{"overview":"Focus on the Orders boundary.","recommendations":[{"title":"Add a boundary",'
        '"why":"Coupling increased.","suggested_action":"Introduce an interface.",'
        '"related_issue_ids":["forbidden-dependency"],"related_files":["src/orders/service.py"]}]}'
    )

    review = OpenAIProvider(model="gpt-5-mini", client=client).review(_context())

    assert review.overview == "Focus on the Orders boundary."
    assert review.recommendations[0].title == "Add a boundary"
    assert review.recommendations[0].related_issue_ids == ["forbidden-dependency"]
    assert len(client.prompts) == 1


def test_invalid_ai_response_has_raw_overview_fallback() -> None:
    review = parse_ai_review_response(
        response="Review the payment boundary.",
        provider="openai",
        model="gpt-5-mini",
    )

    assert review.overview == "Review the payment boundary."
    assert review.recommendations == []
    assert "parsing failed" in review.warnings[0]


def test_pipeline_uses_one_ai_provider_call() -> None:
    provider = _RecordingProvider()
    result = ReviewPipeline(diff=GitDiff(), ai_provider=provider, run_ai=True).run()

    assert result.ai_review is not None
    assert provider.review_calls == 1


def test_ai_config_is_unified_and_rejects_removed_feature_flags(tmp_path: Path) -> None:
    config_path = tmp_path / "sktr.yml"
    config_path.write_text(
        "ai:\n  enabled: true\n  provider: openai\n  model: gpt-5-mini\n",
        encoding="utf-8",
    )
    config = load_config(config_path)

    assert cli_main._ai_enabled(config, None) is True

    config_path.write_text(
        "ai:\n  enabled: true\n  provider: openai\n  features:\n    summary: true\n",
        encoding="utf-8",
    )
    try:
        load_config(config_path)
    except ValidationError as error:
        assert "features" in str(error)
    else:
        raise AssertionError("Expected removed AI feature flags to be rejected")


def test_ai_config_rejects_inconsistent_enabled_state(tmp_path: Path) -> None:
    config_path = tmp_path / "sktr.yml"
    for content in [
        "ai:\n  enabled: true\n",
        "ai:\n  enabled: false\n  provider: openai\n",
    ]:
        config_path.write_text(content, encoding="utf-8")
        try:
            load_config(config_path)
        except ValidationError:
            pass
        else:
            raise AssertionError("Expected inconsistent AI configuration to be rejected")


def test_cli_ai_and_no_ai_select_expected_override(monkeypatch) -> None:
    calls: list[tuple[bool | None, str | None]] = []

    def build(**kwargs) -> ReviewResult:
        calls.append((kwargs["ai_override"], kwargs["model_override"]))
        return ReviewResult(status="foundation ready")

    monkeypatch.setattr(cli_main, "_build_review_result", build)
    with _isolated(Path.cwd() / ".tmp-ai-cli-test"):
        Path("sktr.yml").write_text("project:\n  name: test\n", encoding="utf-8")
        enabled = runner.invoke(cli_main.app, ["review", "--ai"])
        disabled = runner.invoke(cli_main.app, ["review", "--no-ai"])
        selected_model = runner.invoke(cli_main.app, ["review", "--ai", "--model", "gpt-5-mini"])

    assert enabled.exit_code == 0
    assert disabled.exit_code == 0
    assert selected_model.exit_code == 0
    assert calls == [(True, None), (False, None), (True, "gpt-5-mini")]


def test_outputs_and_artifact_use_single_ai_review() -> None:
    result = ReviewResult(status="foundation ready", ai_review=_ai_review())
    terminal = TerminalOutput().render(result)
    markdown = MarkdownOutput().render(result)
    artifact = review_result_to_artifact(result)

    assert "AI Review" in terminal
    assert "[bold]1. Review Orders to Payments[/bold]" in terminal
    assert "## AI Review" in markdown
    assert "### Overview" in markdown
    assert "### Prioritized Actions" in markdown
    assert artifact["ai_review"]["provider"] == "openai"
    assert "ai_advice" not in artifact


def _context() -> AIReviewContext:
    return AIReviewContext(
        review=ReviewContext(
            diff_summary="RAW_SOURCE_SHOULD_NOT_APPEAR",
            file_changes=[FileChange(path="src/orders/service.py", status="modified", added_lines=4)],
        ),
        issues=[
            Issue(
                id="forbidden-dependency",
                title="Forbidden dependency",
                description="Orders imports Payments directly.",
                severity=IssueSeverity.HIGH,
                category=IssueCategory.ARCHITECTURE,
            )
        ],
        system=System(metadata={"knowledge_summary": {"changed_files": 1}}),
    )


def _ai_review() -> AIReview:
    return AIReview(
        provider="openai",
        model="gpt-5-mini",
        overview="Orders gained a payment dependency.",
        recommendations=[
            AIRecommendation(
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
        self.review_calls = 0

    def review(self, context: AIReviewContext) -> AIReview:
        self.review_calls += 1
        return _ai_review()


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
