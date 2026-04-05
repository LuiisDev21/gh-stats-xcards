"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.api.v1.stats_router import router as stats_router
from app.core.config import get_settings
from app.core.exceptions import AppError, app_error_exception_handler
from app.infrastructure.cache import StatsCache
from app.infrastructure.github_client import GithubGraphqlClient
from app.infrastructure.svg_templates import SvgTemplateRenderer
from app.services.github_stats_service import GithubStatsService

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize shared resources and release them on shutdown."""

    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    github_client = GithubGraphqlClient(
        api_url=settings.github_graphql_url,
        token=settings.github_token,
        timeout_seconds=settings.request_timeout_seconds,
    )
    cache = StatsCache[str](
        max_size=settings.cache_max_entries,
        ttl_seconds=settings.cache_ttl_seconds,
    )
    template_renderer = SvgTemplateRenderer(templates_dir=settings.templates_dir)

    app.state.github_stats_service = GithubStatsService(
        github_client=github_client,
        cache=cache,
        template_renderer=template_renderer,
        settings=settings,
    )

    yield

    await github_client.close()


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "HEAD", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Cache-Hit"],
)

app.add_exception_handler(AppError, app_error_exception_handler)
app.include_router(stats_router)


@app.get("/")
async def serve_mini_frontend() -> FileResponse:
    """Sirve la mini interfaz estática para previsualizar tarjetas SVG."""

    index_path = PROJECT_ROOT / "static" / "index.html"
    return FileResponse(path=index_path, media_type="text/html; charset=utf-8")


@app.get("/health", response_class=JSONResponse)
async def healthcheck() -> dict[str, str]:
    """Basic health endpoint."""

    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}

