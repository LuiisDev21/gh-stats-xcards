"""Jinja2 SVG rendering infrastructure."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

from app.core.exceptions import AppError


class TemplateRenderError(AppError):
    """Raised when a template cannot be loaded or rendered."""

    status_code = 500
    code = "template_render_error"


class SvgTemplateRenderer:
    """Render SVG templates from filesystem using Jinja2."""

    def __init__(self, templates_dir: Path) -> None:
        """Initialize renderer.

        Args:
            templates_dir: Directory containing SVG templates.
        """

        self._templates_dir = templates_dir
        # Templates are *.jinja2 with autoescape off: & in URLs (avatars) or names
        # breaks XML when the SVG is parsed as a document (EntityRef: expecting ';').
        self._env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(enabled_extensions=("jinja2", "xml", "html")),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, *, template_name: str, context: dict[str, Any]) -> str:
        """Render an SVG template with context variables.

        Args:
            template_name: Jinja2 template filename.
            context: Template context.

        Returns:
            SVG markup.
        """

        try:
            template = self._env.get_template(template_name)
        except TemplateNotFound as exc:
            raise TemplateRenderError(
                f"SVG template '{template_name}' not found in '{self._templates_dir}'."
            ) from exc

        try:
            return template.render(**context)
        except Exception as exc:  # noqa: BLE001
            raise TemplateRenderError(f"Error rendering SVG '{template_name}'.") from exc

