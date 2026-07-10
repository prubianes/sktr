from sktr_report.artifact import review_result_to_artifact, review_result_to_json, write_review_artifact
from sktr_report.outputs import JsonOutput, MarkdownOutput, TerminalOutput, output_for_format
from sktr_core.plugins import PluginMetadata
from sktr_core.version import SKTR_VERSION


class TerminalOutputPlugin:
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="terminal",
            version=SKTR_VERSION,
            type="output",
            description="Terminal review output.",
        )

    def create_output(self) -> TerminalOutput:
        return TerminalOutput()


class MarkdownOutputPlugin:
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="markdown",
            version=SKTR_VERSION,
            type="output",
            description="Markdown review document output.",
        )

    def create_output(self) -> MarkdownOutput:
        return MarkdownOutput()


class JsonOutputPlugin:
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="json",
            version=SKTR_VERSION,
            type="output",
            description="Canonical JSON review artifact output.",
        )

    def create_output(self) -> JsonOutput:
        return JsonOutput()

__all__ = [
    "JsonOutput",
    "JsonOutputPlugin",
    "MarkdownOutput",
    "MarkdownOutputPlugin",
    "TerminalOutput",
    "TerminalOutputPlugin",
    "output_for_format",
    "review_result_to_artifact",
    "review_result_to_json",
    "write_review_artifact",
]
