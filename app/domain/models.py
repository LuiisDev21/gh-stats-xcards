"""Core domain models used across layers."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.enums import CardType


class ThemeTokens(BaseModel):
    """Color tokens consumed by SVG templates."""

    model_config = ConfigDict(frozen=True)

    bg_color: str
    title_color: str
    text_color: str
    icon_color: str
    border_color: str
    accent_color: str


class GithubUserProfile(BaseModel):
    """Public profile fields fetched from GitHub."""

    model_config = ConfigDict(frozen=True)

    name: str | None
    login: str
    avatar_url: str
    created_at: datetime


class GithubContributionStats(BaseModel):
    """Contribution counters used to render cards."""

    model_config = ConfigDict(frozen=True)

    total_contributions_all_time: int = Field(ge=0)
    total_contributions_current_year: int = Field(ge=0)
    current_year: int = Field(ge=2000)


class LevelInfo(BaseModel):
    """Computed gamification information derived from contribution XP."""

    model_config = ConfigDict(frozen=True)

    level: int = Field(ge=1)
    current_xp: int = Field(ge=0)
    xp_floor: int = Field(ge=0)
    xp_next: int = Field(ge=0)
    progress_percent: float = Field(ge=0.0, le=100.0)
    rank_title: str


class GithubUserStats(BaseModel):
    """Aggregate object for profile and contribution metrics."""

    model_config = ConfigDict(frozen=True)

    profile: GithubUserProfile
    contributions: GithubContributionStats
    level: LevelInfo


class StatsRequestOptions(BaseModel):
    """User-selected options for rendering one SVG card."""

    model_config = ConfigDict(frozen=True)

    username: str
    card_type: CardType = CardType.LEVEL
    theme_name: str = Field(default="dark", min_length=1, max_length=80)
    show_avatar: bool = True
    hide_border: bool = False
    bg_color: str | None = None
    title_color: str | None = None
    text_color: str | None = None
    icon_color: str | None = None
    border_color: str | None = None
    accent_color: str | None = None

    @field_validator("theme_name", mode="before")
    @classmethod
    def _normalize_theme_slug(cls, v: object) -> str:
        if v is None:
            return "dark"
        if hasattr(v, "value"):
            v = getattr(v, "value", v)
        s = str(v).strip().lower().replace("_", "-")
        return s

    @field_validator("theme_name")
    @classmethod
    def _theme_must_exist(cls, v: str) -> str:
        from app.domain.theme_registry import THEMES_BY_SLUG

        if v not in THEMES_BY_SLUG:
            keys = sorted(THEMES_BY_SLUG.keys())
            sample = ", ".join(keys[:24])
            raise ValueError(
                f"Tema desconocido: '{v}'. Hay {len(keys)} temas (p. ej. {sample}, …). "
                "Lista completa: GET /themes"
            )
        return v


class CardRenderResult(BaseModel):
    """Rendered SVG payload and metadata."""

    model_config = ConfigDict(frozen=True)

    svg: str
    cache_key: str
    cache_hit: bool


class ContributionGraphDay(BaseModel):
    """Single calendar day contributions for graphing."""

    model_config = ConfigDict(frozen=True)

    date: str = Field(min_length=10, max_length=10, description="ISO date YYYY-MM-DD")
    count: int = Field(ge=0)


class LanguageSlice(BaseModel):
    """Aggregated primary language share across owned repositories."""

    model_config = ConfigDict(frozen=True)

    name: str
    color: str
    fraction: float = Field(ge=0.0, le=1.0)


class GithubTopRepo(BaseModel):
    """Public repository ranked by stars for the GitHub stats card."""

    model_config = ConfigDict(frozen=True)

    name_with_owner: str
    stargazer_count: int = Field(ge=0)
    display_label: str = ""


class GithubCardActivity(BaseModel):
    """Commit/PR/issue totals and top repos for the GitHub card."""

    model_config = ConfigDict(frozen=True)

    total_commit_contributions: int = Field(ge=0)
    total_pull_request_contributions: int = Field(ge=0)
    total_issue_contributions: int = Field(ge=0)
    top_repos: tuple[GithubTopRepo, ...] = ()

