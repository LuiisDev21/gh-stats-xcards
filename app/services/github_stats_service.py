"""Application service for building GitHub stats SVG cards."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from app.core.config import Settings
from app.domain.enums import CardType
from app.domain.models import (
    CardRenderResult,
    ContributionGraphDay,
    GithubCardActivity,
    GithubContributionStats,
    GithubUserProfile,
    GithubUserStats,
    LanguageSlice,
    LevelInfo,
    StatsRequestOptions,
    ThemeTokens,
)
from app.domain.theme_registry import THEMES_BY_SLUG
from app.infrastructure.cache import StatsCache
from app.infrastructure.github_client import GithubGraphqlClient
from app.infrastructure.svg_templates import SvgTemplateRenderer
from app.utils.chart_helpers import (
    closed_area_under_path,
    cubic_smoothing_path,
    donut_arcs,
    polyline_path,
)
from app.utils.helpers import (
    build_cache_key,
    compute_progress_width,
    donut_palette_for_theme,
    merge_theme_overrides,
)
from app.utils.streak_helpers import (
    StreakMetrics,
    compute_streak_metrics,
    format_long_date,
    format_streak_range,
)


@dataclass(frozen=True)
class _LevelRange:
    """Simple level range descriptor used for rank titles."""

    min_level: int
    title: str


LEVEL_TITLES: tuple[_LevelRange, ...] = (
    _LevelRange(min_level=1, title="Bronze"),
    _LevelRange(min_level=5, title="Silver"),
    _LevelRange(min_level=12, title="Gold"),
    _LevelRange(min_level=20, title="Platinum"),
    _LevelRange(min_level=35, title="Diamond"),
    _LevelRange(min_level=50, title="Legend"),
)


class GithubStatsService:
    """Main use case service for GitHub stats cards."""

    def __init__(
        self,
        *,
        github_client: GithubGraphqlClient,
        cache: StatsCache[str],
        template_renderer: SvgTemplateRenderer,
        settings: Settings,
    ) -> None:
        """Initialize service with its collaborators."""

        self._github_client = github_client
        self._cache = cache
        self._template_renderer = template_renderer
        self._settings = settings

    async def generate_card(self, options: StatsRequestOptions) -> CardRenderResult:
        """Generate an SVG card for the given options.

        Args:
            options: Request options with username/theme/card settings.

        Returns:
            Rendered SVG payload and cache metadata.
        """

        cache_key = build_cache_key(options.model_dump())
        if self._settings.stats_cache_enabled:
            cached_svg = await self._cache.get(cache_key)
            if cached_svg is not None:
                return CardRenderResult(svg=cached_svg, cache_key=cache_key, cache_hit=True)

        theme = self._resolve_theme(options=options)

        if options.card_type == CardType.CONTRIBUTION_GRAPH:
            profile = await self._github_client.fetch_user_profile(options.username)
            days = await self._github_client.fetch_contribution_graph_days(
                options.username,
                num_days=30,
            )
            context = self._build_contribution_graph_context(
                profile=profile,
                days=days,
                theme=theme,
                options=options,
            )
        elif options.card_type == CardType.TOP_LANGUAGES:
            profile = await self._github_client.fetch_user_profile(options.username)
            languages = await self._github_client.fetch_language_slices(options.username)
            context = self._build_top_languages_context(
                profile=profile,
                languages=languages,
                theme=theme,
                options=options,
            )
        elif options.card_type == CardType.STREAK:
            profile = await self._github_client.fetch_user_profile(options.username)
            contributions = await self._github_client.fetch_contribution_stats(
                username=options.username,
                account_created_at=profile.created_at,
            )
            day_map = await self._github_client.fetch_contribution_days_map(
                username=options.username,
                account_created_at=profile.created_at,
            )
            account_start = profile.created_at.astimezone(UTC).date()
            today = datetime.now(UTC).date()
            metrics = compute_streak_metrics(
                day_map,
                account_start=account_start,
                today=today,
            )
            context = self._build_streak_card_context(
                profile=profile,
                contributions=contributions,
                metrics=metrics,
                day_map=day_map,
                theme=theme,
                options=options,
            )
        elif options.card_type in (CardType.GITHUB, CardType.GITHUB_FOOTER):
            profile = await self._github_client.fetch_user_profile(options.username)
            contributions = await self._github_client.fetch_contribution_stats(
                username=options.username,
                account_created_at=profile.created_at,
            )
            level_info = self._calculate_level(contributions.total_contributions_all_time)
            user_stats = GithubUserStats(profile=profile, contributions=contributions, level=level_info)
            activity = await self._github_client.fetch_github_card_activity(
                options.username,
                account_created_at=profile.created_at,
                top_n_repos=self._settings.github_card_top_repos,
            )
            if options.card_type == CardType.GITHUB_FOOTER:
                context = self._build_github_card_footer_context(
                    user_stats=user_stats,
                    activity=activity,
                    theme=theme,
                    options=options,
                )
            else:
                context = self._build_github_card_context(
                    user_stats=user_stats,
                    activity=activity,
                    theme=theme,
                    options=options,
                )
        else:
            profile = await self._github_client.fetch_user_profile(options.username)
            contributions = await self._github_client.fetch_contribution_stats(
                username=options.username,
                account_created_at=profile.created_at,
            )
            level_info = self._calculate_level(contributions.total_contributions_all_time)
            user_stats = GithubUserStats(profile=profile, contributions=contributions, level=level_info)
            context = self._build_level_card_context(
                user_stats=user_stats,
                theme=theme,
                options=options,
            )

        svg = self._template_renderer.render(
            template_name=options.card_type.template_name,
            context=context,
        )
        if self._settings.stats_cache_enabled:
            await self._cache.set(cache_key, svg)
        return CardRenderResult(svg=svg, cache_key=cache_key, cache_hit=False)

    def _is_minimalist(self, options: StatsRequestOptions) -> bool:
        """Return True when the minimalist theme is selected."""

        return options.theme_name == "minimalist"

    def _outer_corner_radius(self, options: StatsRequestOptions) -> int:
        """Border radius for the card rectangle (0 for minimalist)."""

        if self._is_minimalist(options):
            return 0
        if options.card_type == CardType.LEVEL_ALTERNATE:
            return 14
        return 12

    def _bar_corner_radius(self, options: StatsRequestOptions) -> int:
        """Corner radius for progress bars inside level / compact cards."""

        if self._is_minimalist(options):
            return 0
        if options.card_type == CardType.LEVEL:
            return 7
        if options.card_type == CardType.LEVEL_ALTERNATE:
            return 5
        if options.card_type == CardType.GITHUB_FOOTER:
            return 5
        return 4

    def _avatar_inner_radius(self, options: StatsRequestOptions) -> int:
        """Rounded corners for avatar frame in level-alternate card."""

        return 0 if self._is_minimalist(options) else 10

    def _calculate_level(self, xp: int) -> LevelInfo:
        """Calculate level progression from contribution XP."""

        base = max(1, self._settings.level_base_xp)
        level = int(math.sqrt(xp / base)) + 1
        xp_floor = ((level - 1) ** 2) * base
        xp_next = (level**2) * base
        step = max(1, xp_next - xp_floor)
        progress_percent = ((xp - xp_floor) / step) * 100.0
        return LevelInfo(
            level=level,
            current_xp=xp,
            xp_floor=xp_floor,
            xp_next=xp_next,
            progress_percent=max(0.0, min(100.0, progress_percent)),
            rank_title=self._get_rank_title(level),
        )

    def _get_rank_title(self, level: int) -> str:
        """Resolve rank label from level thresholds."""

        title = LEVEL_TITLES[0].title
        for entry in LEVEL_TITLES:
            if level >= entry.min_level:
                title = entry.title
        return title

    def _resolve_theme(self, *, options: StatsRequestOptions) -> ThemeTokens:
        """Apply custom colors on top of selected theme."""

        base_theme = THEMES_BY_SLUG[options.theme_name]
        return merge_theme_overrides(
            base_theme=base_theme,
            overrides={
                "bg_color": options.bg_color,
                "title_color": options.title_color,
                "text_color": options.text_color,
                "icon_color": options.icon_color,
                "border_color": options.border_color,
                "accent_color": options.accent_color,
            },
        )

    def _build_level_card_context(
        self,
        *,
        user_stats: GithubUserStats,
        theme: ThemeTokens,
        options: StatsRequestOptions,
    ) -> dict[str, Any]:
        """Build Jinja2 context for level-style cards."""

        bar_width = self._settings.default_card_width - 48
        progress_width = compute_progress_width(bar_width, user_stats.level.progress_percent)
        corner_radius = self._outer_corner_radius(options)
        bar_corner = self._bar_corner_radius(options)
        avatar_rx = self._avatar_inner_radius(options)
        return {
            "width": self._settings.default_card_width,
            "height": self._settings.default_card_height,
            "corner_radius": corner_radius,
            "bar_corner_radius": bar_corner,
            "avatar_rect_radius": avatar_rx,
            "display_name": user_stats.profile.name or user_stats.profile.login,
            "login": user_stats.profile.login,
            "avatar_url": user_stats.profile.avatar_url,
            "show_avatar": options.show_avatar,
            "hide_border": options.hide_border,
            "total_contributions": user_stats.contributions.total_contributions_all_time,
            "current_year_contributions": user_stats.contributions.total_contributions_current_year,
            "current_year": user_stats.contributions.current_year,
            "level": user_stats.level.level,
            "rank_title": user_stats.level.rank_title,
            "progress_percent_text": f"{user_stats.level.progress_percent:.1f}%",
            "progress_width": progress_width,
            **theme.model_dump(),
        }

    def _build_github_card_context(
        self,
        *,
        user_stats: GithubUserStats,
        activity: GithubCardActivity,
        theme: ThemeTokens,
        options: StatsRequestOptions,
    ) -> dict[str, Any]:
        """Build Jinja2 context for the GitHub card (perfil + actividad + top repos)."""

        width = self._settings.github_card_width
        n_repos = len(activity.top_repos)
        if n_repos == 0:
            last_content_baseline = 182
        else:
            last_content_baseline = 180 + (n_repos - 1) * 18
        level_label_y = last_content_baseline + 20
        bar_y = level_label_y + 16
        height = bar_y + 22
        bar_width = width - 48
        progress_width = compute_progress_width(bar_width, user_stats.level.progress_percent)
        corner_radius = self._outer_corner_radius(options)
        bar_corner = self._bar_corner_radius(options)
        return {
            "width": width,
            "height": height,
            "corner_radius": corner_radius,
            "bar_corner_radius": bar_corner,
            "bar_y": bar_y,
            "display_name": user_stats.profile.name or user_stats.profile.login,
            "login": user_stats.profile.login,
            "avatar_url": user_stats.profile.avatar_url,
            "show_avatar": options.show_avatar,
            "hide_border": options.hide_border,
            "total_contributions": user_stats.contributions.total_contributions_all_time,
            "current_year_contributions": user_stats.contributions.total_contributions_current_year,
            "current_year": user_stats.contributions.current_year,
            "level": user_stats.level.level,
            "rank_title": user_stats.level.rank_title,
            "progress_percent_text": f"{user_stats.level.progress_percent:.1f}%",
            "progress_width": progress_width,
            "level_label_y": level_label_y,
            "total_prs": activity.total_pull_request_contributions,
            "total_issues": activity.total_issue_contributions,
            "top_repos": activity.top_repos,
            **theme.model_dump(),
        }

    def _build_github_card_footer_context(
        self,
        *,
        user_stats: GithubUserStats,
        activity: GithubCardActivity,
        theme: ThemeTokens,
        options: StatsRequestOptions,
    ) -> dict[str, Any]:
        """Tarjeta GitHub ancha para footer (layout horizontal)."""

        width = self._settings.github_card_footer_width
        height = self._settings.github_card_footer_height
        bar_width = width - 56
        progress_width = compute_progress_width(bar_width, user_stats.level.progress_percent)
        corner_radius = self._outer_corner_radius(options)
        bar_corner = self._bar_corner_radius(options)
        bar_y = height - 28
        level_label_y = bar_y - 16
        ring_r = 40.0
        ring_len = 2.0 * math.pi * ring_r
        pct = max(0.0, min(100.0, user_stats.level.progress_percent))
        ring_dashoffset = ring_len * (1.0 - pct / 100.0)
        ring_cx = float(width) - 72.0
        ring_cy = 120.0
        footer_repos = activity.top_repos[:3]
        summary_parts = [
            f"{r.display_label or r.name_with_owner} ({r.stargazer_count})"
            for r in footer_repos
        ]
        top_repos_line = " · ".join(summary_parts) if summary_parts else ""
        if len(top_repos_line) > 118:
            top_repos_line = top_repos_line[:115] + "…"
        return {
            "width": width,
            "height": height,
            "corner_radius": corner_radius,
            "bar_corner_radius": bar_corner,
            "bar_y": bar_y,
            "level_label_y": level_label_y,
            "ring_cx": ring_cx,
            "ring_cy": ring_cy,
            "ring_r": ring_r,
            "ring_len": ring_len,
            "ring_dashoffset": ring_dashoffset,
            "display_name": user_stats.profile.name or user_stats.profile.login,
            "login": user_stats.profile.login,
            "avatar_url": user_stats.profile.avatar_url,
            "show_avatar": options.show_avatar,
            "hide_border": options.hide_border,
            "total_contributions": user_stats.contributions.total_contributions_all_time,
            "current_year_contributions": user_stats.contributions.total_contributions_current_year,
            "current_year": user_stats.contributions.current_year,
            "level": user_stats.level.level,
            "rank_title": user_stats.level.rank_title,
            "progress_percent_text": f"{user_stats.level.progress_percent:.1f}%",
            "progress_width": progress_width,
            "total_prs": activity.total_pull_request_contributions,
            "total_issues": activity.total_issue_contributions,
            "top_repos_line": top_repos_line,
            **theme.model_dump(),
        }

    def _first_contribution_date(self, day_map: dict[str, int], fallback: date) -> date:
        """Earliest calendar day with contributionCount > 0 (GitHub graph semantics)."""

        best: date | None = None
        for key, count in day_map.items():
            if count <= 0:
                continue
            try:
                d = date.fromisoformat(key[:10])
            except ValueError:
                continue
            if best is None or d < best:
                best = d
        return best if best is not None else fallback

    def _build_streak_card_context(
        self,
        *,
        profile: GithubUserProfile,
        contributions: GithubContributionStats,
        metrics: StreakMetrics,
        day_map: dict[str, int],
        theme: ThemeTokens,
        options: StatsRequestOptions,
    ) -> dict[str, Any]:
        """Streak card layout aligned with github-readme-streak-stats (three equal columns)."""

        width = float(self._settings.streak_card_width)
        height = float(self._settings.streak_card_height)
        h_off = (height - 195.0) / 2.0
        col_w = width / 3.0
        total_cx = col_w / 2.0
        current_cx = col_w / 2.0 + col_w
        longest_cx = col_w / 2.0 + 2.0 * col_w
        bar_x0 = col_w
        bar_x1 = 2.0 * col_w
        y_bar_top = 28.0 + h_off / 2.0
        y_bar_bot = 170.0 + h_off
        y_total = [48.0 + h_off, 84.0 + h_off, 114.0 + h_off]
        y_curr_num = 48.0 + h_off
        y_curr_label = 108.0 + h_off
        y_curr_range = 145.0 + h_off
        y_ring_cy = 71.0 + h_off
        y_fire_ty = 19.5 + h_off
        y_longest = [48.0 + h_off, 84.0 + h_off, 114.0 + h_off]

        border_rx = 0.0 if self._is_minimalist(options) else 4.5
        account_start = profile.created_at.astimezone(UTC).date()
        first_contrib = self._first_contribution_date(day_map, account_start)
        total_range = f"{format_long_date(first_contrib)} - Present"
        if (
            metrics.current_streak > 0
            and metrics.current_start is not None
            and metrics.current_end is not None
        ):
            current_range = format_streak_range(metrics.current_start, metrics.current_end)
        else:
            current_range = "—"
        if (
            metrics.longest_streak > 0
            and metrics.longest_start is not None
            and metrics.longest_end is not None
        ):
            longest_range = format_streak_range(metrics.longest_start, metrics.longest_end)
        else:
            longest_range = "—"

        stroke_divider = theme.border_color
        ring_r = 40.0

        return {
            **theme.model_dump(),
            "width": int(width),
            "height": int(height),
            "border_rx": border_rx,
            "rect_w": width - 1.0,
            "rect_h": height - 1.0,
            "hide_border": options.hide_border,
            "total_cx": total_cx,
            "current_cx": current_cx,
            "longest_cx": longest_cx,
            "bar_x0": bar_x0,
            "bar_x1": bar_x1,
            "y_bar_top": y_bar_top,
            "y_bar_bot": y_bar_bot,
            "y_total": y_total,
            "y_curr_num": y_curr_num,
            "y_curr_label": y_curr_label,
            "y_curr_range": y_curr_range,
            "y_ring_cy": y_ring_cy,
            "y_fire_ty": y_fire_ty,
            "y_longest": y_longest,
            "mask_ellipse_cy": 32.0 + h_off,
            "ring_r": ring_r,
            "total_value": f"{contributions.total_contributions_all_time:,}",
            "total_sub": total_range,
            "current_value": f"{metrics.current_streak:,}",
            "current_sub": current_range,
            "longest_value": f"{metrics.longest_streak:,}",
            "longest_sub": longest_range,
            "side_nums": theme.title_color,
            "side_labels": theme.text_color,
            "dates_color": theme.icon_color,
            "curr_streak_label": theme.accent_color,
            "curr_streak_num": theme.title_color,
            "ring_color": theme.accent_color,
            "fire_color": theme.accent_color,
            "divider_stroke": stroke_divider,
        }

    def _build_contribution_graph_context(
        self,
        *,
        profile: GithubUserProfile,
        days: list[ContributionGraphDay],
        theme: ThemeTokens,
        options: StatsRequestOptions,
    ) -> dict[str, Any]:
        """Build Jinja2 context for contribution line graph cards."""

        width = self._settings.contribution_graph_width
        height = self._settings.contribution_graph_height
        corner_radius = self._outer_corner_radius(options)
        minimalist = self._is_minimalist(options)

        pad_left = 58.0
        pad_right = 26.0
        pad_top = 46.0
        pad_bottom = 56.0
        plot_w = float(width) - pad_left - pad_right
        plot_h = float(height) - pad_top - pad_bottom
        baseline_y = pad_top + plot_h

        counts = [d.count for d in days]
        peak = max(counts) if counts else 0
        max_count = max(1, peak)

        n = len(days)
        coords: list[tuple[float, float]] = []
        for index in range(n):
            x = pad_left + (index * (plot_w / max(1, n - 1))) if n > 1 else pad_left + plot_w / 2
            ratio = counts[index] / max_count
            y_coord = pad_top + plot_h - ratio * plot_h
            coords.append((x, y_coord))

        if minimalist or n < 2:
            line_d = polyline_path(coords)
        else:
            line_d = cubic_smoothing_path(coords)

        left_x = coords[0][0] if coords else pad_left
        right_x = coords[-1][0] if coords else pad_left + plot_w
        area_d = ""
        if line_d and not minimalist:
            area_d = closed_area_under_path(
                line_path_d=line_d,
                baseline_y=baseline_y,
                right_x=right_x,
                left_x=left_x,
            )

        circle_dots = [{"cx": px, "cy": py} for px, py in coords]
        grid_cols = 6
        grid_vertical_xs = [
            pad_left + (i / max(1, grid_cols - 1)) * plot_w for i in range(grid_cols)
        ]
        y_ticks: list[dict[str, Any]] = [
            {"y": baseline_y, "label": "0"},
            {"y": pad_top, "label": str(max_count)},
        ]
        if max_count >= 2:
            mid_val = max_count // 2
            mid_y = pad_top + plot_h - (mid_val / max_count) * plot_h
            y_ticks.insert(1, {"y": mid_y, "label": str(mid_val)})

        def day_num(iso: str) -> str:
            parts = iso.split("-")
            return str(int(parts[2])) if len(parts) == 3 else iso

        x_labels: list[dict[str, Any]] = []
        if days and coords and len(days) == len(coords):
            for i, d in enumerate(days):
                x_labels.append({"x": coords[i][0], "label": day_num(d.date)})

        display_name = profile.name or profile.login
        line_color = theme.title_color if minimalist else theme.accent_color
        if minimalist:
            dot_fill = theme.title_color
            dot_stroke = theme.text_color
            dot_stroke_width = 1.2
        else:
            dot_fill = theme.accent_color
            dot_stroke = theme.bg_color
            dot_stroke_width = 2.0

        return {
            "width": width,
            "height": height,
            "corner_radius": corner_radius,
            "hide_border": options.hide_border,
            "graph_title": f"{display_name}'s Contribution Graph",
            "line_path_d": line_d,
            "area_path_d": area_d,
            "show_area_fill": not minimalist,
            "show_chart_grid": not minimalist,
            "circle_dots": circle_dots,
            "grid_vertical_xs": grid_vertical_xs,
            "y_ticks": y_ticks,
            "x_labels": x_labels,
            "plot_pad_left": pad_left,
            "plot_pad_top": pad_top,
            "baseline_y": baseline_y,
            "grid_color": theme.border_color,
            "line_stroke": line_color,
            "line_stroke_width": 2.45 if not minimalist else 1.85,
            "dot_fill": dot_fill,
            "dot_stroke": dot_stroke,
            "dot_stroke_width": dot_stroke_width,
            "dot_radius": 4.2 if not minimalist else 3.6,
            "plot_pad_right": pad_right,
            "graph_title_font_size": 18,
            "graph_title_y": 32,
            "y_axis_label_font_size": 12,
            "y_axis_label_x": 17,
            "y_tick_font_size": 11,
            "x_axis_title_font_size": 12,
            "x_axis_title_y": height - 10,
            "x_labels_y": height - 28,
            "x_label_font_size": 9,
            "grid_stroke_width": 1.15,
            **theme.model_dump(),
        }

    def _build_top_languages_context(
        self,
        *,
        profile: GithubUserProfile,
        languages: list[LanguageSlice],
        theme: ThemeTokens,
        options: StatsRequestOptions,
    ) -> dict[str, Any]:
        """Build Jinja2 context for donut + legend language cards."""

        width = self._settings.chart_card_width
        height = self._settings.chart_card_height
        corner_radius = self._outer_corner_radius(options)
        minimalist = self._is_minimalist(options)

        # Donut más grande respecto a la tarjeta; desplazado a la derecha para no solapar la leyenda.
        shorter = min(float(width), float(height))
        center_x = float(width) * 0.78
        center_y = float(height) * 0.54
        outer_r = shorter * 0.34
        inner_r = outer_r * 0.52

        fractions = [s.fraction for s in languages]
        if options.theme_name in ("default", "dark"):
            palette = [s.color for s in languages]
        else:
            palette = donut_palette_for_theme(theme, len(languages))
        arcs = donut_arcs(
            center_x=center_x,
            center_y=center_y,
            outer_radius=outer_r,
            inner_radius=inner_r,
            fractions=fractions,
            colors=palette,
        )

        legend_items: list[dict[str, str]] = []
        for entry, slice_color in zip(languages, palette, strict=True):
            pct = round(entry.fraction * 100.0)
            legend_items.append(
                {
                    "name": entry.name,
                    "color": slice_color,
                    "percent": f"{pct}%",
                }
            )

        login = profile.login
        return {
            "width": width,
            "height": height,
            "corner_radius": corner_radius,
            "hide_border": options.hide_border,
            "card_title": "Top Languages by Repo",
            "subtitle": f"@{login}",
            "donut_slices": arcs,
            "legend_items": legend_items,
            "has_language_data": len(languages) > 0,
            "legend_percent_x": int(width * 0.42),
            "swatch_radius": 0 if minimalist else 2,
            "donut_stroke": "none" if minimalist else theme.border_color,
            "donut_stroke_width": 0.0 if minimalist else 0.45,
            **theme.model_dump(),
        }
