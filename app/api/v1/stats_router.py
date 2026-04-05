"""API routes for SVG stats cards."""

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response

from app.core.config import Settings
from app.core.dependencies import get_app_settings, get_github_stats_service
from app.domain.enums import CardType, ThemeName
from app.domain.models import StatsRequestOptions
from app.services.github_stats_service import GithubStatsService

router = APIRouter(tags=["stats"])


@router.get("/stats/{username}", response_class=Response)
async def get_stats_svg(
    username: str = Path(
        ...,
        min_length=1,
        max_length=39,
        pattern=r"^[a-zA-Z0-9-]+$",
        description="GitHub username",
    ),
    theme: ThemeName = Query(default=ThemeName.DARK),
    card: CardType = Query(default=CardType.LEVEL),
    show_avatar: bool = Query(default=True),
    hide_border: bool = Query(default=False),
    bg_color: str | None = Query(default=None),
    title_color: str | None = Query(default=None),
    text_color: str | None = Query(default=None),
    icon_color: str | None = Query(default=None),
    border_color: str | None = Query(default=None),
    accent_color: str | None = Query(default=None),
    service: GithubStatsService = Depends(get_github_stats_service),
    settings: Settings = Depends(get_app_settings),
) -> Response:
    """Return a GitHub stats card as SVG.

    Args:
        username: GitHub username.
        theme: Built-in theme selector.
        card: Card variant selector.
        show_avatar: Toggle avatar visibility in SVG.
        hide_border: Hide card border when true.
        bg_color: Optional custom background color.
        title_color: Optional custom title color.
        text_color: Optional custom body text color.
        icon_color: Optional custom icon color.
        border_color: Optional custom border color.
        accent_color: Optional custom accent color.
        service: Business service dependency.
        settings: Application settings dependency.

    Returns:
        SVG payload with image content type.
    """

    try:
        options = StatsRequestOptions(
            username=username,
            card_type=card,
            theme_name=theme,
            show_avatar=show_avatar,
            hide_border=hide_border,
            bg_color=bg_color,
            title_color=title_color,
            text_color=text_color,
            icon_color=icon_color,
            border_color=border_color,
            accent_color=accent_color,
        )
        rendered = await service.generate_card(options)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if settings.stats_cache_enabled:
        cache_control = f"public, max-age={settings.cache_ttl_seconds}"
    else:
        cache_control = "no-store"
    headers = {
        "Cache-Control": cache_control,
        "X-Cache-Hit": str(rendered.cache_hit).lower(),
    }
    return Response(
        content=rendered.svg,
        media_type="image/svg+xml; charset=utf-8",
        headers=headers,
    )

