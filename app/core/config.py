"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the API service.

    Attributes:
        app_name: Human-readable app name used in OpenAPI docs.
        app_version: Semantic version exposed by health endpoint and docs.
        environment: Runtime environment label (local, staging, production).
        log_level: Logging level used by the standard logging module.
        github_graphql_url: GitHub GraphQL endpoint URL.
        github_token: Personal access token used to authenticate requests.
        request_timeout_seconds: Timeout for outbound requests to GitHub.
        cache_max_entries: Maximum number of cache entries held in memory.
        cache_ttl_seconds: Time-to-live for each cache entry in seconds.
        stats_cache_enabled: When false, skips the in-memory stats cache (e.g. while editing SVG templates).
        templates_dir: Directory containing Jinja2 SVG templates.
        level_base_xp: XP curve factor used to calculate user level.
        default_card_width: Default SVG card width.
        default_card_height: Default SVG card height.
        chart_card_width: Width for chart-style cards (e.g. top languages).
        chart_card_height: Height for chart-style cards (e.g. top languages).
        contribution_graph_width: Width for the contribution graph SVG (e.g. README footer).
        contribution_graph_height: Height for the contribution graph SVG.
        github_card_width: Width for the compact GitHub card SVG.
        github_card_height: Mínimo de altura (la tarjeta crece con los repos; el slack inferior se recorta al contenido).
        github_card_top_repos: Number of top public repos to show (by stars).
        github_card_footer_width: Ancho de la tarjeta GitHub horizontal (footer / README).
        github_card_footer_height: Alto de la tarjeta GitHub horizontal.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "GitHub Stats API"
    app_version: str = "1.0.0"
    environment: str = "local"
    log_level: str = "INFO"

    github_graphql_url: str = "https://api.github.com/graphql"
    github_token: str | None = None
    request_timeout_seconds: float = 20.0

    cache_max_entries: int = 2048
    cache_ttl_seconds: int = 21600
    stats_cache_enabled: bool = True

    templates_dir: Path = Field(default=Path("templates/svg"))
    level_base_xp: int = 100
    default_card_width: int = 495
    default_card_height: int = 195
    chart_card_width: int = 540
    chart_card_height: int = 220
    contribution_graph_width: int = 900
    contribution_graph_height: int = 280
    github_card_width: int = 495
    github_card_height: int = 240
    github_card_top_repos: int = 5
    github_card_footer_width: int = 900
    github_card_footer_height: int = 248


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton settings instance."""

    return Settings()

