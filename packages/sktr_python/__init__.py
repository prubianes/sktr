from sktr_python.analyzer import PythonAstAnalyzer
from sktr_core.plugins import PluginMetadata


class PythonAnalyzerPlugin:
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="sktr-python",
            version="0.10.0",
            type="analyzer",
            description="Python analyzer using the standard ast module.",
        )

    def create_analyzer(self) -> PythonAstAnalyzer:
        return PythonAstAnalyzer()


__all__ = ["PythonAnalyzerPlugin", "PythonAstAnalyzer"]
