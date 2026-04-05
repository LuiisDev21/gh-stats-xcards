"""Utility helpers shared by service and API layers."""

from __future__ import annotations

import re
from hashlib import sha256
from typing import Any

from app.domain.models import ThemeTokens

HEX_COLOR_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")


def normalize_hex_color(value: str | None) -> str | None:
    """Normalize a hex color to ``#RRGGBB`` format.

    Args:
        value: Optional user-provided color string.

    Returns:
        Normalized color or ``None`` when input is absent.

    Raises:
        ValueError: If the color is not a valid 6-digit hex value.
    """

    if value is None:
        return None
    candidate = value.strip()
    if not HEX_COLOR_RE.match(candidate):
        raise ValueError(f"Color inválido: '{value}'. Usa formato #RRGGBB.")
    return candidate if candidate.startswith("#") else f"#{candidate}"


def merge_theme_overrides(base_theme: ThemeTokens, overrides: dict[str, str | None]) -> ThemeTokens:
    """Merge user color overrides onto a base theme.

    Args:
        base_theme: Built-in theme colors.
        overrides: Optional override values.

    Returns:
        New theme token set with validated overrides applied.
    """

    normalized: dict[str, str] = {}
    for key, value in overrides.items():
        if value is None:
            continue
        normalized_value = normalize_hex_color(value)
        if normalized_value is not None:
            normalized[key] = normalized_value
    return base_theme.model_copy(update=normalized)


def build_cache_key(parts: dict[str, Any]) -> str:
    """Build a deterministic cache key from arbitrary request parts."""

    serialized = "|".join(f"{key}={parts[key]}" for key in sorted(parts.keys()))
    digest = sha256(serialized.encode("utf-8")).hexdigest()
    return f"stats:{digest}"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    raw = hex_color.strip().lstrip("#")
    if len(raw) != 6:
        msg = f"Color hex inválido (se esperan 6 dígitos): '{hex_color}'"
        raise ValueError(msg)
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"


def mix_hex(color_a: str, color_b: str, t: float) -> str:
    """Interpola linealmente dos colores ``#RRGGBB`` en RGB (t=0 → a, t=1 → b)."""

    t = max(0.0, min(1.0, t))
    a = _hex_to_rgb(color_a)
    b = _hex_to_rgb(color_b)
    return _rgb_to_hex(tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)))


def _blend_toward_white(rgb: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    amount = max(0.0, min(1.0, amount))
    return tuple(int(c + (255 - c) * amount) for c in rgb)


def _blend_toward_black(rgb: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    amount = max(0.0, min(1.0, amount))
    return tuple(int(c * (1.0 - amount)) for c in rgb)


def brighten_hex(hex_color: str, amount: float) -> str:
    """Aclara un ``#RRGGBB`` mezclando hacia blanco."""

    return _rgb_to_hex(_blend_toward_white(_hex_to_rgb(hex_color), amount))


def darken_hex(hex_color: str, amount: float) -> str:
    """Oscurece un ``#RRGGBB`` multiplicando hacia negro."""

    return _rgb_to_hex(_blend_toward_black(_hex_to_rgb(hex_color), amount))


def donut_palette_for_theme(theme: ThemeTokens, count: int) -> list[str]:
    """Genera ``count`` colores de relleno para el donut a partir del tema.

    En temas monocromáticos (p. ej. minimalist) usa una escala de grises legible
    sobre fondo claro; en el resto, combina accent, title, icon y border.
    """

    if count < 1:
        return []
    chroma_keys = {theme.accent_color, theme.title_color, theme.icon_color, theme.text_color}
    if len(chroma_keys) == 1:
        ramp = ["#070707", "#222222", "#3c3c3c", "#565656", "#717171", "#8b8b8b"]
        return [ramp[i % len(ramp)] for i in range(count)]

    bor = theme.border_color
    txt = theme.text_color
    seeds = [
        theme.accent_color,
        darken_hex(theme.accent_color, 0.3),
        brighten_hex(theme.accent_color, 0.18),
        theme.title_color,
        darken_hex(theme.title_color, 0.25),
        theme.icon_color,
        darken_hex(theme.icon_color, 0.2),
        mix_hex(theme.accent_color, bor, 0.12),
        mix_hex(bor, theme.icon_color, 0.35),
        mix_hex(theme.title_color, txt, 0.55),
        brighten_hex(theme.icon_color, 0.12),
    ]
    return [seeds[i % len(seeds)] for i in range(count)]


def compute_progress_width(total_width: int, progress_percent: float) -> int:
    """Compute progress bar width based on percentage.

    Args:
        total_width: Total bar width in pixels.
        progress_percent: Percentage in [0, 100].

    Returns:
        Integer width in pixels.
    """

    normalized = max(0.0, min(100.0, progress_percent))
    return int((normalized / 100.0) * total_width)

