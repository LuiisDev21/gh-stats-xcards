"""Dependency providers for FastAPI endpoints."""

from fastapi import Request

from app.core.config import Settings, get_settings
from app.services.github_stats_service import GithubStatsService


def get_app_settings() -> Settings:
    """Provide application settings singleton."""

    return get_settings()


def get_github_stats_service(request: Request) -> GithubStatsService:
    """Provide a request-scoped handle to the shared service instance."""

    return request.app.state.github_stats_service

