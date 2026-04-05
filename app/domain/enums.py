"""Domain enumerations for supported cards and themes."""

from enum import Enum


class CardType(str, Enum):
    """Supported SVG card variants."""

    LEVEL = "level"
    LEVEL_ALTERNATE = "level-alternate"
    GITHUB = "github"
    GITHUB_FOOTER = "github-footer"
    CONTRIBUTION_GRAPH = "contribution-graph"
    TOP_LANGUAGES = "top-languages"

    @property
    def template_name(self) -> str:
        """Map card type to Jinja2 template filename."""

        mapping: dict["CardType", str] = {
            CardType.LEVEL: "level_card.jinja2",
            CardType.LEVEL_ALTERNATE: "level_alternate.jinja2",
            CardType.GITHUB: "github_card.jinja2",
            CardType.GITHUB_FOOTER: "github_card_footer.jinja2",
            CardType.CONTRIBUTION_GRAPH: "contribution_graph.jinja2",
            CardType.TOP_LANGUAGES: "top_languages.jinja2",
        }
        return mapping[self]


class ThemeName(str, Enum):
    """Supported built-in theme names."""

    DEFAULT = "default"
    DARK = "dark"
    TOKYONIGHT = "tokyonight"
    RADICAL = "radical"
    DRACULA = "dracula"
    VISION_FRIENDLY_DARK = "vision-friendly-dark"
    MINIMALIST = "minimalist"
    VUE = "vue"

