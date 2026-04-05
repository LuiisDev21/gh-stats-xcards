"""Catálogo de temas: definición interna en `themes_catalog` + ajustes de app."""

from __future__ import annotations

from app.domain.models import ThemeTokens
from app.domain.themes_catalog import THEMES_BUILTIN

THEMES_BY_SLUG: dict[str, ThemeTokens] = dict(THEMES_BUILTIN)

THEMES_BY_SLUG["minimalist"] = ThemeTokens(
    bg_color="#ffffff",
    title_color="#000000",
    text_color="#000000",
    icon_color="#000000",
    border_color="#000000",
    accent_color="#000000",
)
THEMES_BY_SLUG["vue"] = ThemeTokens(
    bg_color="#15251f",
    title_color="#42d392",
    text_color="#c8e6d0",
    icon_color="#6fd9a8",
    border_color="#2a4d41",
    accent_color="#42b883",
)
