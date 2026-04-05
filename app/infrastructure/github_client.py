"""Async GitHub GraphQL client used by the application service."""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import httpx

from app.core.exceptions import GithubApiError, GithubRateLimitError, GithubUserNotFound
from app.domain.models import (
    ContributionGraphDay,
    GithubCardActivity,
    GithubContributionStats,
    GithubTopRepo,
    GithubUserProfile,
    LanguageSlice,
)

LOGGER = logging.getLogger(__name__)

PROFILE_QUERY = """
query UserProfile($login: String!) {
  user(login: $login) {
    name
    login
    avatarUrl
    createdAt
  }
}
"""

CONTRIBUTION_RANGE_QUERY = """
query ContributionRange($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
      }
    }
  }
}
"""

CONTRIBUTION_CALENDAR_WEEKS_QUERY = """
query ContributionCalendarWeeks($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""

GITHUB_CARD_CONTRIBUTIONS_SLICE_QUERY = """
query GithubCardContributionsSlice($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
    }
  }
}
"""

GITHUB_CARD_TOP_REPOS_QUERY = """
query GithubCardTopRepos($login: String!, $repoFirst: Int!) {
  user(login: $login) {
    repositories(
      first: $repoFirst
      ownerAffiliations: OWNER
      privacy: PUBLIC
      isFork: false
      orderBy: {field: STARGAZERS, direction: DESC}
    ) {
      nodes {
        nameWithOwner
        stargazerCount
      }
    }
  }
}
"""

REPO_LANGUAGES_PAGE_QUERY = """
query UserRepoLanguages($login: String!, $first: Int!, $after: String) {
  user(login: $login) {
    repositories(
      first: $first
      after: $after
      ownerAffiliations: OWNER
      isFork: false
      orderBy: {field: UPDATED_AT, direction: DESC}
    ) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        primaryLanguage {
          name
          color
        }
      }
    }
  }
}
"""


class GithubGraphqlClient:
    """GitHub GraphQL API adapter.

    This class encapsulates all networking concerns and transforms raw payloads
    into domain-level models.
    """

    def __init__(
        self,
        *,
        api_url: str,
        token: str | None,
        timeout_seconds: float,
    ) -> None:
        """Initialize the client.

        Args:
            api_url: GraphQL endpoint URL.
            token: GitHub token used to authenticate requests.
            timeout_seconds: HTTP timeout in seconds.
        """

        headers: dict[str, str] = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        self._api_url = api_url
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            headers=headers,
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""

        await self._http_client.aclose()

    async def fetch_user_profile(self, username: str) -> GithubUserProfile:
        """Fetch public user profile fields from GitHub.

        Args:
            username: GitHub login name.

        Returns:
            Parsed user profile model.
        """

        data = await self._execute_query(PROFILE_QUERY, {"login": username})
        user_data = data.get("user")
        if user_data is None:
            raise GithubUserNotFound(f"El usuario '{username}' no existe en GitHub.")

        return GithubUserProfile(
            name=user_data.get("name"),
            login=user_data["login"],
            avatar_url=user_data["avatarUrl"],
            created_at=datetime.fromisoformat(user_data["createdAt"].replace("Z", "+00:00")),
        )

    async def fetch_contribution_stats(
        self,
        *,
        username: str,
        account_created_at: datetime,
    ) -> GithubContributionStats:
        """Fetch yearly and lifetime contribution counts.

        Args:
            username: GitHub login name.
            account_created_at: Account creation date to establish year range.

        Returns:
            Contribution aggregate for current year and all-time.
        """

        now_utc = datetime.now(UTC)
        current_year_start = datetime(year=now_utc.year, month=1, day=1, tzinfo=UTC)

        current_year_total = await self._fetch_contributions_for_range(
            username=username,
            from_dt=current_year_start,
            to_dt=now_utc,
        )

        first_year = account_created_at.astimezone(UTC).year
        years = list(range(first_year, now_utc.year + 1))
        totals = await asyncio.gather(
            *[self._fetch_contributions_for_year(username=username, year=year) for year in years]
        )
        all_time_total = sum(totals)

        return GithubContributionStats(
            total_contributions_all_time=all_time_total,
            total_contributions_current_year=current_year_total,
            current_year=now_utc.year,
        )

    async def _fetch_contributions_for_year(self, *, username: str, year: int) -> int:
        """Fetch total contributions for one calendar year."""

        from_dt = datetime(year=year, month=1, day=1, tzinfo=UTC)
        to_dt = datetime(year=year, month=12, day=31, hour=23, minute=59, second=59, tzinfo=UTC)
        return await self._fetch_contributions_for_range(
            username=username,
            from_dt=from_dt,
            to_dt=to_dt,
        )

    async def _fetch_contributions_for_range(
        self,
        *,
        username: str,
        from_dt: datetime,
        to_dt: datetime,
    ) -> int:
        """Fetch contribution count for a date range."""

        variables = {
            "login": username,
            "from": from_dt.isoformat().replace("+00:00", "Z"),
            "to": to_dt.isoformat().replace("+00:00", "Z"),
        }
        data = await self._execute_query(CONTRIBUTION_RANGE_QUERY, variables)
        user_data = data.get("user")
        if user_data is None:
            raise GithubUserNotFound(f"El usuario '{username}' no existe en GitHub.")

        contribution_total = (
            user_data.get("contributionsCollection", {})
            .get("contributionCalendar", {})
            .get("totalContributions", 0)
        )
        return int(contribution_total)

    async def fetch_contribution_graph_days(
        self,
        username: str,
        *,
        num_days: int = 30,
    ) -> list[ContributionGraphDay]:
        """Return daily contribution counts for the last ``num_days`` (inclusive).

        Args:
            username: GitHub login name.
            num_days: Number of calendar days to include ending today (minimum 1).

        Returns:
            Ordered list from oldest to newest day within the window.
        """

        if num_days < 1:
            num_days = 1
        now_utc = datetime.now(UTC)
        start_day: date = (now_utc - timedelta(days=num_days - 1)).date()
        from_dt = datetime.combine(start_day, time.min, tzinfo=UTC)

        variables = {
            "login": username,
            "from": from_dt.isoformat().replace("+00:00", "Z"),
            "to": now_utc.isoformat().replace("+00:00", "Z"),
        }
        data = await self._execute_query(CONTRIBUTION_CALENDAR_WEEKS_QUERY, variables)
        user_payload = data.get("user")
        if user_payload is None:
            raise GithubUserNotFound(f"El usuario '{username}' no existe en GitHub.")

        count_by_calendar_day: dict[str, int] = {}
        weeks = (
            user_payload.get("contributionsCollection", {})
            .get("contributionCalendar", {})
            .get("weeks", [])
        )
        for week in weeks:
            for day_entry in week.get("contributionDays", []):
                day_key = str(day_entry.get("date", ""))[:10]
                count_by_calendar_day[day_key] = int(day_entry.get("contributionCount", 0))

        series: list[ContributionGraphDay] = []
        for offset in range(num_days):
            current = start_day + timedelta(days=offset)
            key = current.isoformat()
            series.append(
                ContributionGraphDay(
                    date=key,
                    count=count_by_calendar_day.get(key, 0),
                )
            )
        return series

    async def _fetch_github_card_contribution_slice(
        self,
        *,
        username: str,
        from_dt: datetime,
        to_dt: datetime,
    ) -> tuple[int, int, int]:
        """Return (commits, prs, issues) for a range; GitHub exige ``to - from`` ≤ 1 año."""

        variables = {
            "login": username,
            "from": from_dt.isoformat().replace("+00:00", "Z"),
            "to": to_dt.isoformat().replace("+00:00", "Z"),
        }
        data = await self._execute_query(GITHUB_CARD_CONTRIBUTIONS_SLICE_QUERY, variables)
        user_payload = data.get("user")
        if user_payload is None:
            raise GithubUserNotFound(f"El usuario '{username}' no existe en GitHub.")
        cc = user_payload.get("contributionsCollection") or {}
        return (
            int(cc.get("totalCommitContributions") or 0),
            int(cc.get("totalPullRequestContributions") or 0),
            int(cc.get("totalIssueContributions") or 0),
        )

    async def fetch_github_card_activity(
        self,
        username: str,
        *,
        account_created_at: datetime,
        top_n_repos: int = 5,
    ) -> GithubCardActivity:
        """Fetch commit/PR/issue totals (vida de la cuenta) y top repos.

        ``contributionsCollection`` solo admite rangos de hasta un año; se suman
        intervalos por año natural (mismo criterio que las contribuciones totales).
        """

        now_utc = datetime.now(UTC)
        start = account_created_at.astimezone(UTC).replace(microsecond=0)
        end = now_utc.replace(microsecond=0)

        commits = prs = issues = 0
        first_year = start.year
        last_year = end.year
        for year in range(first_year, last_year + 1):
            year_start = datetime(year, 1, 1, tzinfo=UTC)
            year_end = datetime(year, 12, 31, 23, 59, 59, tzinfo=UTC)
            from_dt = max(start, year_start)
            to_dt = min(end, year_end)
            if from_dt > to_dt:
                continue
            c, p, i = await self._fetch_github_card_contribution_slice(
                username=username,
                from_dt=from_dt,
                to_dt=to_dt,
            )
            commits += c
            prs += p
            issues += i

        repo_vars: dict[str, Any] = {
            "login": username,
            "repoFirst": max(1, min(10, top_n_repos)),
        }
        data = await self._execute_query(GITHUB_CARD_TOP_REPOS_QUERY, repo_vars)
        user_payload = data.get("user")
        if user_payload is None:
            raise GithubUserNotFound(f"El usuario '{username}' no existe en GitHub.")

        repo_nodes = (user_payload.get("repositories") or {}).get("nodes") or []
        top: list[GithubTopRepo] = []
        max_label = 36
        for node in repo_nodes:
            if not node:
                continue
            nwo = str(node.get("nameWithOwner") or "").strip()
            if not nwo:
                continue
            stars = int(node.get("stargazerCount") or 0)
            label = nwo if len(nwo) <= max_label else nwo[: max_label - 1] + "…"
            top.append(
                GithubTopRepo(
                    name_with_owner=nwo,
                    stargazer_count=stars,
                    display_label=label,
                )
            )

        return GithubCardActivity(
            total_commit_contributions=commits,
            total_pull_request_contributions=prs,
            total_issue_contributions=issues,
            top_repos=tuple(top),
        )

    async def fetch_language_slices(
        self,
        username: str,
        *,
        page_size: int = 100,
        max_pages: int = 4,
    ) -> list[LanguageSlice]:
        """Aggregate primary-language counts over non-fork repositories owned by the user.

        Args:
            username: GitHub login name.
            page_size: GraphQL page size for repositories (max 100).
            max_pages: Safety cap on pagination depth.

        Returns:
            Up to six slices (top five languages plus optional ``Other`` bucket).
        """

        counts: Counter[str] = Counter()
        color_by_lang: dict[str, str] = {}
        cursor: str | None = None

        for _ in range(max_pages):
            variables: dict[str, Any] = {
                "login": username,
                "first": min(100, page_size),
                "after": cursor,
            }
            data = await self._execute_query(REPO_LANGUAGES_PAGE_QUERY, variables)
            user_payload = data.get("user")
            if user_payload is None:
                raise GithubUserNotFound(f"El usuario '{username}' no existe en GitHub.")

            repo_conn = user_payload.get("repositories", {})
            for node in repo_conn.get("nodes", []):
                primary = node.get("primaryLanguage")
                if not primary or not primary.get("name"):
                    continue
                lang_name = str(primary["name"])
                counts[lang_name] += 1
                color_by_lang.setdefault(lang_name, str(primary.get("color") or "#666666"))

            page_info = repo_conn.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")
            if not cursor:
                break

        total = sum(counts.values())
        if total == 0:
            return []

        slices: list[LanguageSlice] = []
        most_common = counts.most_common(5)
        accounted = 0
        for name, raw_count in most_common:
            fraction = raw_count / total
            accounted += raw_count
            slices.append(
                LanguageSlice(
                    name=name,
                    color=color_by_lang.get(name, "#666666"),
                    fraction=fraction,
                )
            )

        other_count = total - accounted
        if other_count > 0 and len(counts) > 5:
            slices.append(
                LanguageSlice(
                    name="Other",
                    color="#888888",
                    fraction=other_count / total,
                )
            )
        return slices

    async def _execute_query(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """Execute a GraphQL operation and return the `data` section.

        Args:
            query: GraphQL operation.
            variables: GraphQL variables dictionary.

        Returns:
            GraphQL data payload.
        """

        payload = {"query": query, "variables": variables}
        try:
            response = await self._http_client.post(self._api_url, json=payload)
        except httpx.HTTPError as exc:
            LOGGER.exception("Error de red consultando GitHub GraphQL: %s", exc)
            raise GithubApiError("No se pudo conectar con GitHub GraphQL API.") from exc

        if response.status_code == 401:
            raise GithubApiError("Token de GitHub inválido o ausente para GraphQL API.")
        if response.status_code == 403:
            raise GithubRateLimitError("GitHub API limitó temporalmente la solicitud.")
        if response.status_code >= 400:
            raise GithubApiError(
                f"GitHub GraphQL respondió con estado inesperado: {response.status_code}."
            )

        raw_payload: dict[str, Any] = response.json()
        errors = raw_payload.get("errors", [])
        if errors:
            joined_messages = " | ".join(str(err.get("message", "")) for err in errors)
            if "Could not resolve to a User" in joined_messages:
                raise GithubUserNotFound("No se encontró el usuario en GitHub.")
            if "rate limit" in joined_messages.lower():
                raise GithubRateLimitError("GitHub GraphQL alcanzó el límite de consumo.")

            LOGGER.error("GraphQL errors: %s", joined_messages)
            raise GithubApiError(f"GitHub GraphQL devolvió errores: {joined_messages}")

        data = raw_payload.get("data")
        if not isinstance(data, dict):
            raise GithubApiError("Respuesta inválida de GitHub GraphQL (sin campo data).")
        return data

