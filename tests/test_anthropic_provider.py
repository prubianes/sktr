from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from sktr_ai import AnthropicProvider, resolve_anthropic_api_key
from sktr_ai.anthropic_provider import MessagesAPIClient, _extract_message_text
from sktr_cli.main import app
from sktr_core.plugins import AIReviewContext

runner = CliRunner()


def test_sktr_anthropic_api_key_is_used_when_present(monkeypatch) -> None:
    monkeypatch.setenv("SKTR_ANTHROPIC_API_KEY", "sktr-secret")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    resolution = resolve_anthropic_api_key()

    assert resolution.value == "sktr-secret"
    assert resolution.source == "SKTR_ANTHROPIC_API_KEY"


def test_anthropic_api_key_is_used_as_fallback(monkeypatch) -> None:
    monkeypatch.delenv("SKTR_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fallback-secret")

    resolution = resolve_anthropic_api_key()

    assert resolution.value == "fallback-secret"
    assert resolution.source == "ANTHROPIC_API_KEY"


def test_sktr_anthropic_api_key_overrides_anthropic_api_key(monkeypatch) -> None:
    monkeypatch.setenv("SKTR_ANTHROPIC_API_KEY", "sktr-secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fallback-secret")

    review = AnthropicProvider(model="claude-sonnet-5", client=_FakeClient("Summary")).review(
        AIReviewContext()
    )

    assert review.metadata["api_key_source"] == "SKTR_ANTHROPIC_API_KEY"
    assert review.model == "claude-sonnet-5"
    assert "fallback-secret" not in review.metadata.values()


def test_missing_key_returns_a_warning(monkeypatch) -> None:
    monkeypatch.delenv("SKTR_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    review = AnthropicProvider().review(AIReviewContext())

    assert review.warnings == [
        "Anthropic provider is configured, but no API key was found. "
        "Set SKTR_ANTHROPIC_API_KEY or ANTHROPIC_API_KEY to enable AI features."
    ]
    assert review.metadata["api_key_status"] == "missing"


def test_anthropic_timeout_becomes_a_provider_warning(monkeypatch) -> None:
    monkeypatch.setenv("SKTR_ANTHROPIC_API_KEY", "test-key")

    def timeout(*args, **kwargs):
        raise TimeoutError("The read operation timed out")

    monkeypatch.setattr("sktr_ai.anthropic_provider.urlopen", timeout)

    review = AnthropicProvider(client=MessagesAPIClient()).review(AIReviewContext())

    assert review.overview is None
    assert review.warnings == ["Anthropic AI Review unavailable: Anthropic request could not be completed"]


def test_messages_api_client_extracts_text_blocks() -> None:
    body = {
        "stop_reason": "end_turn",
        "content": [
            {"type": "text", "text": "First recommendation. "},
            {"type": "text", "text": "Second recommendation."},
        ],
    }

    assert _extract_message_text(body) == "First recommendation. Second recommendation."


def test_ai_doctor_reports_anthropic_source_without_printing_secret(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SKTR_ANTHROPIC_API_KEY", "do-not-print-this-secret")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config = tmp_path / "sktr.yml"
    config.write_text(
        "ai:\n  enabled: true\n  provider: anthropic\n  model: claude-sonnet-5\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["ai", "doctor", "--config", str(config)])

    assert result.exit_code == 0
    assert "AI provider: anthropic" in result.output
    assert "AI model: claude-sonnet-5" in result.output
    assert "API key: found via SKTR_ANTHROPIC_API_KEY" in result.output
    assert "do-not-print-this-secret" not in result.output


def test_ai_doctor_explains_missing_anthropic_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("SKTR_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config = tmp_path / "sktr.yml"
    config.write_text(
        "ai:\n  enabled: true\n  provider: anthropic\n  model: claude-sonnet-5\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["ai", "doctor", "--config", str(config)])

    assert result.exit_code == 0
    assert "API key: missing" in result.output
    assert "SKTR_ANTHROPIC_API_KEY or ANTHROPIC_API_KEY" in result.output


class _FakeClient:
    def __init__(self, response: str) -> None:
        self.response = response

    def generate(self, *, prompt: str, model: str, api_key: str) -> str:
        return self.response
