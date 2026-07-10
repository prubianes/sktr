from sktr_python.analyzer import PythonAstAnalyzer
from sktr_core.plugins import PluginMetadata
from sktr_core.version import SKTR_VERSION


class PythonAnalyzerPlugin:
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="sktr-python",
            version=SKTR_VERSION,
            type="analyzer",
            description="Python analyzer using the standard ast module.",
        )

    def create_analyzer(self) -> PythonAstAnalyzer:
        return PythonAstAnalyzer()


__all__ = ["PythonAnalyzerPlugin", "PythonAstAnalyzer"]
