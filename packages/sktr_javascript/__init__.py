from sktr_core.plugins import PluginMetadata
from sktr_core.version import SKTR_VERSION
from sktr_javascript.analyzer import JavaScriptTypeScriptAnalyzer


class JavaScriptTypeScriptAnalyzerPlugin:
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="sktr-javascript-typescript",
            version=SKTR_VERSION,
            type="analyzer",
            description="JavaScript and TypeScript analyzer using Tree-sitter.",
        )

    def create_analyzer(self) -> JavaScriptTypeScriptAnalyzer:
        return JavaScriptTypeScriptAnalyzer()


__all__ = ["JavaScriptTypeScriptAnalyzer", "JavaScriptTypeScriptAnalyzerPlugin"]
