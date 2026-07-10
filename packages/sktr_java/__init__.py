from sktr_core.plugins import PluginMetadata
from sktr_core.version import SKTR_VERSION
from sktr_java.analyzer import JavaAnalyzer


class JavaAnalyzerPlugin:
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="sktr-java",
            version=SKTR_VERSION,
            type="analyzer",
            description="Java analyzer using Tree-sitter.",
        )

    def create_analyzer(self) -> JavaAnalyzer:
        return JavaAnalyzer()


__all__ = ["JavaAnalyzer", "JavaAnalyzerPlugin"]
