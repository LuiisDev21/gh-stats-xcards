"""Pure helpers to build SVG path data for charts."""

from __future__ import annotations

import math
from collections.abc import Sequence


def cubic_smoothing_path(points: Sequence[tuple[float, float]]) -> str:
    """Build an open SVG path using cubic Bézier segments between points.

    Args:
        points: Series of (x, y) coordinates in pixel space.

    Returns:
        SVG ``d`` attribute for a stroked path. Empty string if fewer than two points.
    """

    if len(points) < 2:
        return ""
    segments: list[str] = [f"M {points[0][0]:.2f} {points[0][1]:.2f}"]
    for idx in range(len(points) - 1):
        x_0, y_0 = points[idx]
        x_1, y_1 = points[idx + 1]
        delta_x = (x_1 - x_0) / 3.0
        c1_x = x_0 + delta_x
        c1_y = y_0
        c2_x = x_1 - delta_x
        c2_y = y_1
        segments.append(f"C {c1_x:.2f} {c1_y:.2f} {c2_x:.2f} {c2_y:.2f} {x_1:.2f} {y_1:.2f}")
    return " ".join(segments)


def polyline_path(points: Sequence[tuple[float, float]]) -> str:
    """Build a straight polyline ``d`` value."""

    if len(points) < 2:
        return ""
    first_x, first_y = points[0]
    body = " ".join(f"L {x:.2f} {y:.2f}" for x, y in points[1:])
    return f"M {first_x:.2f} {first_y:.2f} {body}"


def closed_area_under_path(*, line_path_d: str, baseline_y: float, right_x: float, left_x: float) -> str:
    """Close a line path down to a horizontal baseline to form a fillable area.

    Args:
        line_path_d: Open path in pixel space, must start with M at the leftmost point.
        baseline_y: Y coordinate of the chart baseline.
        right_x: X of the last sample (right edge).
        left_x: X of the first sample (left edge).

    Returns:
        Closed path suitable for filling under the line.
    """

    if not line_path_d:
        return ""
    return f"{line_path_d} L {right_x:.2f} {baseline_y:.2f} L {left_x:.2f} {baseline_y:.2f} Z"


def donut_arcs(
    *,
    center_x: float,
    center_y: float,
    outer_radius: float,
    inner_radius: float,
    fractions: Sequence[float],
    colors: Sequence[str],
) -> list[dict[str, str]]:
    """Compute annular sector paths for a donut chart.

    Args:
        center_x: Horizontal center in pixels.
        center_y: Vertical center in pixels.
        outer_radius: Outer radius.
        inner_radius: Inner radius (hole).
        fractions: Non-negative shares that sum to ~1.0 (values <= 0 are skipped).
        colors: Fill color per slice (CSS color / hex).

    Returns:
        List of dicts with keys ``d`` and ``fill`` for SVG ``<path>`` elements.
    """

    slices: list[dict[str, str]] = []
    total = sum(max(0.0, f) for f in fractions)
    if total <= 0:
        return slices
    angle = -math.pi / 2
    for frac, color in zip(fractions, colors, strict=True):
        share = max(0.0, frac) / total
        if share <= 0:
            continue
        sweep = 2 * math.pi * share
        end_angle = angle + sweep
        large = 1 if sweep > math.pi else 0
        x_outer_1 = center_x + outer_radius * math.cos(angle)
        y_outer_1 = center_y + outer_radius * math.sin(angle)
        x_outer_2 = center_x + outer_radius * math.cos(end_angle)
        y_outer_2 = center_y + outer_radius * math.sin(end_angle)
        x_inner_2 = center_x + inner_radius * math.cos(end_angle)
        y_inner_2 = center_y + inner_radius * math.sin(end_angle)
        x_inner_1 = center_x + inner_radius * math.cos(angle)
        y_inner_1 = center_y + inner_radius * math.sin(angle)
        path_d = (
            f"M {x_outer_1:.2f} {y_outer_1:.2f} "
            f"A {outer_radius:.2f} {outer_radius:.2f} 0 {large} 1 {x_outer_2:.2f} {y_outer_2:.2f} "
            f"L {x_inner_2:.2f} {y_inner_2:.2f} "
            f"A {inner_radius:.2f} {inner_radius:.2f} 0 {large} 0 {x_inner_1:.2f} {y_inner_1:.2f} Z"
        )
        slices.append({"d": path_d, "fill": color})
        angle = end_angle
    return slices
