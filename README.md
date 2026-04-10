# GitHub Stats xCards

Render **SVG profile cards** from live GitHub data: contribution totals, level progression, repository highlights, language mix, and more. Built with **FastAPI**, **Jinja2**, and the **GitHub GraphQL API**.

Embed cards in your profile README or any page that accepts images.

---

## Table of contents

- [Quick embed](#quick-embed)
- [Demo cards](#demo-cards)
- [Live preview](#live-preview)
- [API](#api)
- [Card types](#card-types)
- [Themes](#themes)
- [Query parameters](#query-parameters)
- [How numbers are computed](#how-numbers-are-computed)
- [Caching](#caching)
- [Self-hosting](#self-hosting)
- [Development](#development)

---

## Quick embed

1. Replace `YOUR_USERNAME` with your GitHub login and `https://YOUR_DEPLOYMENT` with your instance base URL.
2. Paste into your profile README (or any Markdown that loads remote images).

```markdown
[![GitHub Stats xCards](https://YOUR_DEPLOYMENT/stats/YOUR_USERNAME?card=level&theme=dark)](https://github.com/YOUR_USERNAME)
```

**Image-only URL** (for HTML or other uses):

```text
https://YOUR_DEPLOYMENT/stats/YOUR_USERNAME?card=github&theme=tokyonight&show_avatar=true
```

**README avatars:** with `show_avatar=true`, the API embeds the profile photo inside the SVG (data URI) so GitHub does not block external avatar URLs referenced from SVG cards.

---

## Demo cards


### Level

[![Level card](https://gh-stats-xcards.fly.dev/stats/torvalds?card=level&theme=dark)](https://gh-stats-xcards.fly.dev/stats/torvalds?card=level&theme=dark)

### Level alternate

[![Level alternate card](https://gh-stats-xcards.fly.dev/stats/torvalds?card=level-alternate&theme=dark)](https://gh-stats-xcards.fly.dev/stats/torvalds?card=level-alternate&theme=dark)

### GitHub (vertical)

[![GitHub card](https://gh-stats-xcards.fly.dev/stats/torvalds?card=github&theme=dark&show_avatar=true)](https://gh-stats-xcards.fly.dev/stats/torvalds?card=github&theme=dark&show_avatar=true)

### GitHub footer (wide)

[![GitHub footer card](https://gh-stats-xcards.fly.dev/stats/torvalds?card=github-footer&theme=dark&show_avatar=true)](https://gh-stats-xcards.fly.dev/stats/torvalds?card=github-footer&theme=dark&show_avatar=true)

### Contribution graph

[![Contribution graph card](https://gh-stats-xcards.fly.dev/stats/torvalds?card=contribution-graph&theme=dark)](https://gh-stats-xcards.fly.dev/stats/torvalds?card=contribution-graph&theme=dark)

### Streak

[![Streak card](https://gh-stats-xcards.fly.dev/stats/torvalds?card=streak&theme=dark)](https://gh-stats-xcards.fly.dev/stats/torvalds?card=streak&theme=dark)

### Top languages

[![Top languages card](https://gh-stats-xcards.fly.dev/stats/torvalds?card=top-languages&theme=dark)](https://gh-stats-xcards.fly.dev/stats/torvalds?card=top-languages&theme=dark)

---

## Live preview

After you run the app locally, open the root URL to use the bundled UI:

`http://127.0.0.1:8000/`

Interactive API docs: `/docs` (Swagger) and `/redoc`.

---

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/stats/{username}` | Returns one SVG card (see query parameters). |
| `GET` | `/themes` | JSON: `themes` (slugs), `count`, `palettes` (per-slug hex tokens for UI swatches). |
| `GET` | `/` | Static preview page (`static/index.html`). |
| `GET` | `/health` | JSON health check. |

- **Response type:** `image/svg+xml; charset=utf-8`
- **Username:** GitHub handle (`a-z`, `A-Z`, `0-9`, `-`), max length 39.

---

## Card types

Set the variant with `card=` in the query string.

| Value | Description |
|-------|-------------|
| `level` | Default. Level, rank title, total & year contributions, progress bar. |
| `level-alternate` | Alternate layout for the level card. |
| `github` | Vertical card: profile, contribution stats, PR/issue totals, top public repos (by stars). |
| `github-footer` | Wide horizontal card suited for README footers; shows top **3** repos in one line and a level ring. |
| `contribution-graph` | Line/area chart of recent contribution activity. |
| `streak` | Three-column card modeled on [github-readme-streak-stats](https://github.com/DenverCoder1/github-readme-streak-stats): total (from **first contribution day**), current streak (ring + fire icon + pop-in number animation), longest streak; column dividers and staggered `fadein` like the PHP demo ([streak-stats.demolab.com](https://streak-stats.demolab.com)). |
| `top-languages` | Donut chart of primary languages across your public repositories. |

Default if omitted: `level`.

---

## Themes

Set with `theme=`. The slug must exist in the built-in catalog (`app/domain/themes_catalog.py`); **`GET /themes`** returns the current list as JSON. Overrides and extra slugs (e.g. `minimalist`) live in `app/domain/theme_registry.py`.

**Examples:** `default`, `dark` (API default), `tokyonight`, `radical`, `dracula`, `vision-friendly-dark`, **`pastel`** (soft pink), **`minimalist`**, **`vue`** (dark green).

Custom hex colors (see below) override individual tokens on top of the chosen theme.

---

## Query parameters

All parameters are optional except the path `username`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `theme` | string | `dark` | One of the [themes](#themes). |
| `card` | string | `level` | One of the [card types](#card-types). |
| `show_avatar` | boolean | `true` | Show profile avatar when the template supports it. |
| `hide_border` | boolean | `false` | Hide the card border. |
| `bg_color` | hex | _(theme)_ | Background (`#RRGGBB` or `RRGGBB`). |
| `title_color` | hex | _(theme)_ | Title / headings. |
| `text_color` | hex | _(theme)_ | Body text. |
| `icon_color` | hex | _(theme)_ | Icons and some accents. |
| `border_color` | hex | _(theme)_ | Border and dividers. |
| `accent_color` | hex | _(theme)_ | Progress bars, highlights, chart accents. |

Invalid hex values return `422` with a short error message.

### Example

```text
/stats/octocat?card=github-footer&theme=dracula&show_avatar=true&accent_color=50fa7b
```

---

## How numbers are computed

- Data comes from the **GitHub GraphQL API** (server-side). A **personal access token** increases rate limits and is required for reliable production hosting (see [Self-hosting](#self-hosting)).
- **Contributions** follow GitHub’s contribution graph rules (commits, issues, PRs, reviews, etc., subject to visibility and profile settings). Private contributions appear only if enabled on your GitHub profile.
- **Level & rank** use your **all-time contribution total** as XP, with:

  \[
  \text{level} = \left\lfloor \sqrt{\frac{\text{XP}}{\text{base}}} \right\rfloor + 1
  \]

  `base` defaults to `100` and can be changed via `LEVEL_BASE_XP` in the environment (see settings in `app/core/config.py`).

- **Rank titles** (by level thresholds): Bronze → Silver → Gold → Platinum → Diamond → Legend.
- **Top repositories** on `github` cards use your **public** repos ranked by **stars** (count configured server-side, default top 5; footer card uses top 3 in the summary line).
- Graph and language cards aggregate **public** repository metadata as implemented in the GitHub client.

For GitHub’s own rules on what counts as a contribution, see GitHub’s documentation on profile contributions.

---

## Caching

Successful SVG responses may include:

- `Cache-Control: public, max-age=<seconds>` when `STATS_CACHE_ENABLED=true` (default TTL **6 hours**, `21600` seconds).
- Header `X-Cache-Hit: true|false`.

Disable caching while iterating on templates: set `STATS_CACHE_ENABLED=false`.

---

## Self-hosting

### Requirements

- **Python 3.12.x** (recommended; avoid 3.14 for `pydantic-core` wheel issues on many platforms). The repo includes `runtime.txt` and `.python-version` as hints.
- Optional but strongly recommended: **GitHub personal access token** (classic or fine-grained with read access to what you need).

### Environment variables

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | Token sent as `Authorization: Bearer` to GitHub GraphQL. |
| `GITHUB_GRAPHQL_URL` | Override API URL (default `https://api.github.com/graphql`). |
| `STATS_CACHE_ENABLED` | `true` / `false` (default `true`). |
| `CACHE_TTL_SECONDS` | Cache TTL in seconds (default `21600`). |
| `LEVEL_BASE_XP` | Level curve base (default `100`). |
| `GITHUB_CARD_TOP_REPOS` | Top-N repos on the vertical `github` card (default `5`). |
| `STREAK_CARD_WIDTH` / `STREAK_CARD_HEIGHT` | SVG size for `streak` (defaults **`495` × `195`**, same proportions as [github-readme-streak-stats](https://github.com/DenverCoder1/github-readme-streak-stats)). |

See `app/core/config.py` for the full list and defaults.

### Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export GITHUB_TOKEN=ghp_xxxxxxxx   # optional for dev; required for production traffic
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Or use `./run.sh` for the same app with reload on port `8000` (or `PORT`).

### Docker

Build and run (minimal image, Python 3.12):

```bash
docker build -t gh-stats-xcards .
docker run --rm -p 8000:8000 -e GITHUB_TOKEN=ghp_xxxxxxxx gh-stats-xcards
```

Or use Compose (reads the host environment; optionally add `--env-file .env`):

```bash
docker compose up --build
```

- **`PORT`**: defaults to `8000`; platforms like Fly/Render usually inject `PORT`.
- `.env` is not baked into the image; pass secrets with `-e`, `--env-file`, or your orchestrator’s secrets.

### Deploy (generic PaaS)

- **Build:** `pip install -r requirements.txt`
- **Start:** `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`

Do **not** use `--reload` in production.

On **Render**, place `runtime.txt` in the repo root (already included) so the build uses Python 3.12.x. Set `PORT` from the platform if required.

**Fly.io** (example): `fly launch` with the `Dockerfile`, machine `internal_port` = `8000`, and set `PORT=8000` if the template does not set it.

---

## Development

- SVG templates live in `templates/svg/` (Jinja2).
- Core API route: `app/api/v1/stats_router.py`.
- Domain enums: `app/domain/enums.py` (`CardType`).
- Themes: `app/domain/themes_catalog.py` (`THEMES_BUILTIN`); `app/domain/theme_registry.py` merges overrides into `THEMES_BY_SLUG`.

---

## License

MIT. See `LICENSE`.

---

*GitHub Stats xCards is an independent project. For another take on profile stats cards (different stack and feature set), see community projects such as [awesome-github-stats](https://github.com/brunobritodev/awesome-github-stats).*
