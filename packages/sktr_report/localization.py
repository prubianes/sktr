from __future__ import annotations

from dataclasses import dataclass

from sktr_core.localization import deterministic_language, normalize_language_tag
from sktr_core.model import Issue

_ES = {
    "review": "Revisión de SKTR",
    "summary": "Resumen",
    "risk": "Riesgo",
    "score": "Puntuación",
    "changed_files": "Archivos modificados",
    "excluded_files": "Archivos excluidos",
    "issues": "Hallazgos",
    "review_breadth": "Alcance de la revisión: {production_files} archivos de producción en {modules} módulos",
    "review_state": "Estado de la revisión",
    "no_tracked_changes": "No se encontraron cambios rastreados.",
    "untracked_guidance": "Los archivos sin seguimiento no están incluidos. Añádelos con `git add` antes de ejecutar la revisión.",
    "no_branch_changes": "No se encontraron cambios para la comparación de rama seleccionada.",
    "no_commit_changes": "No se encontraron cambios para el commit seleccionado.",
    "no_scope_changes": "No se encontraron cambios para este alcance de revisión.",
    "findings": "Hallazgos",
    "findings_by_category": "Hallazgos por categoría",
    "analysis_diagnostics": "Diagnósticos de análisis",
    "suggested_actions": "Acciones sugeridas",
    "notes": "Notas",
    "metadata": "Metadatos",
    "generated_by": "Generado por SKTR.",
    "status": "Estado",
    "generated_at": "Generado el",
    "review_scope": "Alcance de la revisión",
    "repository_root": "Raíz del repositorio",
    "language": "Idioma",
    "language_fallback": (
        "El idioma `{requested}` no tiene un catálogo completo; el texto determinista "
        "se muestra en inglés y el contenido de IA se solicita en `{requested}`."
    ),
    "ai_review": "Revisión con IA",
    "overview": "Resumen general",
    "prioritized_actions": "Acciones priorizadas",
    "warning": "Advertencia",
    "why": "Motivo",
    "suggested_action": "Acción sugerida",
    "related_files": "Archivos relacionados",
    "occurrences": "{count} apariciones",
    "affected_files": "Archivos afectados",
    "category": "Categoría",
    "highest_severity": "Severidad máxima",
    "rules": "Reglas",
    "severity": "Severidad",
    "analyzer": "Analizador",
    "file": "Archivo",
    "message": "Mensaje",
    "more": "{count} más",
    "reason": "Motivo",
    "imports": "{source} importa {target}",
    "imports_markdown": "`{source}` importa `{target}`.",
    "function_lines": "{symbol} tiene {count} líneas.",
    "function_lines_markdown": "`{symbol}` tiene {count} líneas.",
}

_SEVERITIES_ES = {
    "critical": "Crítica",
    "high": "Alta",
    "medium": "Media",
    "low": "Baja",
    "info": "Informativa",
    "warning": "Advertencia",
    "error": "Error",
}

_CATEGORIES_ES = {
    "architecture": "Arquitectura",
    "coupling": "Acoplamiento",
    "modularity": "Modularidad",
    "maintainability": "Mantenibilidad",
    "testing": "Pruebas",
    "documentation": "Documentación",
    "unknown": "Desconocida",
}

_ISSUE_TITLES_ES = {
    "new_dependency": "Nueva dependencia detectada",
    "large_file": "Superficie de cambio extensa",
    "large_function": "Función extensa detectada",
    "forbidden_dependency": "Dependencia prohibida",
    "dependency_cycle": "Ciclo de dependencias detectado",
    "high_fan_out": "Alto fan-out del módulo",
    "public_api_change": "Símbolo de API pública eliminado",
    "missing_tests": "Cambios de código fuente sin cambios en pruebas",
}

_MESSAGES_ES = {
    "No analyzers configured yet.": "Aún no hay analizadores configurados.",
    "No rules configured yet.": "Aún no hay reglas configuradas.",
    "No AI provider configured yet.": "Aún no hay un proveedor de IA configurado.",
}

_SUGGESTIONS_ES = {
    "Consider extracting cohesive responsibilities into smaller functions.": (
        "Considera extraer responsabilidades cohesivas en funciones más pequeñas."
    ),
    "Route the dependency through the configured boundary instead of importing it directly.": (
        "Dirige la dependencia a través del límite configurado en lugar de importarla directamente."
    ),
    "Add or update focused tests for the changed behavior.": (
        "Añade o actualiza pruebas específicas para el comportamiento modificado."
    ),
}


@dataclass(frozen=True)
class Translator:
    requested: str
    language: str

    @classmethod
    def for_language(cls, requested: str) -> "Translator":
        normalized = normalize_language_tag(requested)
        return cls(requested=normalized, language=deterministic_language(normalized))

    def text(self, key: str, english: str, **values: object) -> str:
        template = _ES.get(key, english) if self.language == "es" else english
        return template.format(**values)

    def severity(self, value: str) -> str:
        if self.language == "es":
            return _SEVERITIES_ES.get(value, value)
        return value.title()

    def category(self, value: str) -> str:
        if self.language == "es":
            return _CATEGORIES_ES.get(value, value)
        return value.title()

    def issue_title(self, issue: Issue) -> str:
        if self.language != "es":
            return issue.title
        return _ISSUE_TITLES_ES.get(str(issue.metadata.get("rule_key", "")), issue.title)

    def issue_description(self, issue: Issue) -> str:
        if self.language != "es":
            return issue.description
        metadata = issue.metadata
        rule_key = metadata.get("rule_key")
        if rule_key == "new_dependency":
            count = int(metadata.get("dependency_count", "1"))
            paths = [path for path in str(metadata.get("paths", "")).split(",") if path]
            imports = "una importación" if count == 1 else f"{count} importaciones"
            files = "un archivo" if len(paths) == 1 else f"{len(paths)} archivos"
            return (
                f"{metadata.get('source', '')} añadió {imports} a "
                f"{metadata.get('target', '')} en {files}."
            )
        if rule_key == "large_file":
            return (
                f"{metadata.get('path', '')} cambió "
                f"{metadata.get('changed_lines', '0')} líneas."
            )
        if rule_key == "large_function":
            return (
                f"{metadata.get('symbol', issue.title)} en {metadata.get('path', '')} "
                f"tiene {metadata.get('line_count', '0')} líneas."
            )
        if rule_key == "forbidden_dependency":
            reason = metadata.get("reason") or "Esto infringe las reglas de dependencia configuradas."
            return (
                f"{metadata.get('source', '')} importa {metadata.get('target', '')}.\n"
                f"Motivo:\n{reason}"
            )
        if rule_key == "dependency_cycle":
            return f"Ciclo de dependencias entre módulos detectado: {metadata.get('cycle', '')}."
        if rule_key == "high_fan_out":
            return (
                f"El módulo {metadata.get('module', '')} depende de "
                f"{metadata.get('fan_out', '0')} módulos adicionales."
            )
        if rule_key == "public_api_change":
            return (
                f"{metadata.get('symbol', '')} fue eliminado de "
                f"{metadata.get('path', '')}."
            )
        if rule_key == "missing_tests":
            affected = [path for path in str(metadata.get("affected_files", "")).split(",") if path]
            return (
                f"{len(affected)} archivos de código fuente cambiaron sin cambios "
                "correspondientes en archivos de pruebas."
            )
        return issue.description

    def message(self, value: str) -> str:
        return _MESSAGES_ES.get(value, value) if self.language == "es" else value

    def suggestion(self, value: str) -> str:
        return _SUGGESTIONS_ES.get(value, value) if self.language == "es" else value

    def status(self, value: str) -> str:
        if self.language == "es" and value == "review complete":
            return "revisión completa"
        return value

    def scope(self, value: str) -> str:
        if self.language != "es":
            return value
        return {
            "working_tree": "árbol de trabajo",
            "branch": "rama",
            "commit": "commit",
        }.get(value, value)
