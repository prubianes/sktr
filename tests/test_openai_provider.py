from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from sktr_ai import OpenAIProvider, resolve_openai_api_key
from sktr_ai.openai_provider import ResponsesAPIClient, _extract_output_text
from sktr_cli.main import app
from sktr_core.plugins import AIReviewContext

runner = CliRunner()


def test_sktr_openai_api_key_is_used_when_present(monkeypatch) -> None:
    monkeypatch.setenv("SKTR_OPENAI_API_KEY", "sktr-secret")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    resolution = resolve_openai_api_key()

    assert resolution.value == "sktr-secret"
    assert resolution.source == "SKTR_OPENAI_API_KEY"


def test_openai_api_key_is_used_as_fallback(monkeypatch) -> None:
    monkeypatch.delenv("SKTR_OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "fallback-secret")

    resolution = resolve_openai_api_key()

    assert resolution.value == "fallback-secret"
    assert resolution.source == "OPENAI_API_KEY"


def test_sktr_openai_api_key_overrides_openai_api_key(monkeypatch) -> None:
    monkeypatch.setenv("SKTR_OPENAI_API_KEY", "sktr-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "fallback-secret")

    review = OpenAIProvider(model="gpt-5-mini", client=_FakeClient("Summary")).review(AIReviewContext())

    assert review.metadata["api_key_source"] == "SKTR_OPENAI_API_KEY"
    assert review.model == "gpt-5-mini"
    assert "fallback-secret" not in review.metadata.values()


def test_missing_key_returns_a_warning(monkeypatch) -> None:
    monkeypatch.delenv("SKTR_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    review = OpenAIProvider().review(AIReviewContext())

    assert review.warnings == [
        "OpenAI provider is configured, but no API key was found. "
        "Set SKTR_OPENAI_API_KEY or OPENAI_API_KEY to enable AI features."
    ]
    assert review.metadata["api_key_status"] == "missing"


def test_openai_timeout_becomes_a_provider_warning(monkeypatch) -> None:
    monkeypatch.setenv("SKTR_OPENAI_API_KEY", "test-key")

    def timeout(*args, **kwargs):
        raise TimeoutError("The read operation timed out")

    monkeypatch.setattr("sktr_ai.openai_provider.urlopen", timeout)

    review = OpenAIProvider(client=ResponsesAPIClient()).review(AIReviewContext())

    assert review.overview is None
    assert review.warnings == ["OpenAI AI Review unavailable: OpenAI request could not be completed"]


def test_responses_api_client_extracts_nested_output_text() -> None:
    body = {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": "First recommendation. "},
                    {"type": "output_text", "text": "Second recommendation."},
                ],
            }
        ],
    }

    assert _extract_output_text(body) == "First recommendation. Second recommendation."


def test_ai_doctor_reports_source_without_printing_secret(monkeypatch) -> None:
    monkeypatch.setenv("SKTR_OPENAI_API_KEY", "do-not-print-this-secret")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with _isolated(Path.cwd() / ".tmp-ai-doctor-test"):
        Path("sktr.yml").write_text(
            "ai:\n  enabled: true\n  provider: openai\n",
            encoding="utf-8",
        )

        result = runner.invoke(app, ["ai", "doctor"])

    assert result.exit_code == 0
    assert "API key: found via SKTR_OPENAI_API_KEY" in result.output
    assert "do-not-print-this-secret" not in result.output


def test_ai_doctor_missing_key_explains_resolution_without_printing_secrets(monkeypatch) -> None:
    monkeypatch.delenv("SKTR_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with _isolated(Path.cwd() / ".tmp-ai-doctor-missing-test"):
        Path("sktr.yml").write_text(
            "ai:\n  enabled: true\n  provider: openai\n",
            encoding="utf-8",
        )
        result = runner.invoke(app, ["ai", "doctor"])

    assert result.exit_code == 0
    assert "API key: missing" in result.output
    assert "SKTR_OPENAI_API_KEY or OPENAI_API_KEY" in result.output
    assert "sktr ai doctor" in result.output


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


class _FakeClient:
    def __init__(self, response: str) -> None:
        self.response = response

    def generate(self, *, prompt: str, model: str, api_key: str) -> str:
        return self.response
