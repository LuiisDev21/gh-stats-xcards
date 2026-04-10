"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response

from app.api.v1.stats_router import router as stats_router
from app.domain.models import ThemeTokens
from app.domain.theme_registry import THEMES_BY_SLUG
from app.core.config import get_settings
from app.core.exceptions import AppError, app_error_exception_handler
from app.infrastructure.cache import StatsCache
from app.infrastructure.github_client import GithubGraphqlClient
from app.infrastructure.svg_templates import SvgTemplateRenderer
from app.services.github_stats_service import GithubStatsService

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_BASE_URL = "https://xcards.duckdns.org"


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


@app.get("/robots.txt")
async def robots_txt() -> Response:
    """Robots directives for search crawlers."""

    body = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Sitemap: https://xcards.duckdns.org/sitemap.xml",
            "",
        ]
    )
    return Response(content=body, media_type="text/plain; charset=utf-8")


@app.get("/sitemap.xml")
async def sitemap_xml() -> Response:
    """Minimal sitemap for primary crawlable endpoints."""

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{PUBLIC_BASE_URL}/</loc>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>{PUBLIC_BASE_URL}/themes</loc>
    <changefreq>weekly</changefreq>
    <priority>0.6</priority>
  </url>
  <url>
    <loc>{PUBLIC_BASE_URL}/stats/torvalds?card=github&amp;theme=dark&amp;show_avatar=true</loc>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>
</urlset>
"""
    return Response(content=xml, media_type="application/xml; charset=utf-8")


def _theme_tokens_public(t: ThemeTokens) -> dict[str, str]:
    """Hex tokens for UI swatches (e.g. static preview)."""

    return {
        "bg_color": t.bg_color,
        "title_color": t.title_color,
        "text_color": t.text_color,
        "icon_color": t.icon_color,
        "border_color": t.border_color,
        "accent_color": t.accent_color,
    }


@app.get("/themes", response_class=JSONResponse)
async def list_theme_slugs() -> dict[str, object]:
    """Theme slugs plus optional `palettes` dict for color swatches in the preview UI."""

    themes = sorted(THEMES_BY_SLUG.keys())
    palettes = {slug: _theme_tokens_public(t) for slug, t in THEMES_BY_SLUG.items()}
    return {"themes": themes, "count": len(themes), "palettes": palettes}

