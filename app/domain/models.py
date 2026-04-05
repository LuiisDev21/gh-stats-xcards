"""Core domain models used across layers."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import CardType, ThemeName


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
    theme_name: ThemeName = ThemeName.DARK
    show_avatar: bool = True
    hide_border: bool = False
    bg_color: str | None = None
    title_color: str | None = None
    text_color: str | None = None
    icon_color: str | None = None
    border_color: str | None = None
    accent_color: str | None = None


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


THEMES: dict[ThemeName, ThemeTokens] = {
    ThemeName.DEFAULT: ThemeTokens(
        bg_color="#ffffff",
        title_color="#24292f",
        text_color="#57606a",
        icon_color="#0969da",
        border_color="#d0d7de",
        accent_color="#1f6feb",
    ),
    ThemeName.DARK: ThemeTokens(
        bg_color="#0d1117",
        title_color="#58a6ff",
        text_color="#c9d1d9",
        icon_color="#8b949e",
        border_color="#30363d",
        accent_color="#2f81f7",
    ),
    ThemeName.TOKYONIGHT: ThemeTokens(
        bg_color="#1a1b27",
        title_color="#70a5fd",
        text_color="#a9b1d6",
        icon_color="#bf91f3",
        border_color="#2f334d",
        accent_color="#7aa2f7",
    ),
    ThemeName.RADICAL: ThemeTokens(
        bg_color="#141321",
        title_color="#fe428e",
        text_color="#a9fef7",
        icon_color="#f8d847",
        border_color="#332f57",
        accent_color="#f8d847",
    ),
    ThemeName.DRACULA: ThemeTokens(
        bg_color="#282a36",
        title_color="#ff79c6",
        text_color="#f8f8f2",
        icon_color="#bd93f9",
        border_color="#44475a",
        accent_color="#50fa7b",
    ),
    ThemeName.VISION_FRIENDLY_DARK: ThemeTokens(
        bg_color="#0f0f0f",
        title_color="#ffb000",
        text_color="#e6edf3",
        icon_color="#79c0ff",
        border_color="#3d444d",
        accent_color="#ffd33d",
    ),
    ThemeName.MINIMALIST: ThemeTokens(
        bg_color="#ffffff",
        title_color="#000000",
        text_color="#000000",
        icon_color="#000000",
        border_color="#000000",
        accent_color="#000000",
    ),
    ThemeName.VUE: ThemeTokens(
        bg_color="#15251f",
        title_color="#42d392",
        text_color="#c8e6d0",
        icon_color="#6fd9a8",
        border_color="#2a4d41",
        accent_color="#42b883",
    ),
}

