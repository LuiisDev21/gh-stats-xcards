# GitHub Stats API (FastAPI + Clean Architecture)

API en Python 3.11+ para generar tarjetas SVG de estadísticas de GitHub, inspirada en `awesome-github-stats` y `github-readme-stats`, con arquitectura limpia, render Jinja2 y caché TTL.

## Características

- FastAPI asíncrono con tipado completo (`type hints` en todo el código).
- Arquitectura en capas: `core`, `domain`, `infrastructure`, `services`, `api`.
- Consulta a GitHub GraphQL API para perfil, contribuciones del año actual y total histórico.
- Cálculo de nivel estilo XP (`total contributions -> level -> progress`).
- Render de SVG con Jinja2 (`level`, `level-alternate`, `github`).
- Temas predefinidos y colores personalizados por query params.
- Caché en memoria de 6 horas con `cachetools.TTLCache`.
- Logging estructurado y manejo de errores con excepciones de aplicación.

## Estructura

```text
github-stats-api/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── dependencies.py
│   │   └── exceptions.py
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   └── enums.py
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── github_client.py
│   │   ├── cache.py
│   │   └── svg_templates.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── github_stats_service.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── stats_router.py
│   └── utils/
│       ├── __init__.py
│       ├── helpers.py
│       └── chart_helpers.py
├── templates/
│   └── svg/
│       ├── level_card.jinja2
│       ├── level_alternate.jinja2
│       ├── github_card.jinja2
│       ├── contribution_graph.jinja2
│       └── top_languages.jinja2
├── static/
│   └── index.html
├── .env.example
├── requirements.txt
├── README.md
└── run.sh
```

## Requisitos

- Python 3.11 o superior
- Token de GitHub con acceso de lectura para GraphQL API (`GITHUB_TOKEN`)

## Instalación local

```bash
cd /Users/luis/Desktop/gh-stats-xcards/github-stats-api
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Edita `.env` y define un token válido en `GITHUB_TOKEN`.

## Ejecución local

```bash
cd /Users/luis/Desktop/gh-stats-xcards/github-stats-api
source .venv/bin/activate
bash run.sh
```

También puedes usar:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Mini interfaz web

Con el servicio en ejecución, abre en el navegador `http://127.0.0.1:8000/` (ruta `GET /`). Verás un formulario que construye la URL de `GET /stats/{username}`, solicita el SVG con `fetch` y lo muestra en la página (si la API devuelve JSON de error, se muestra el cuerpo del mensaje).

Si abres `static/index.html` como `file://`, el frontend usa por defecto `http://127.0.0.1:8000` como base del API (CORS del backend habilitado para desarrollo).

## Uso de la API

Endpoint principal:

- `GET /stats/{username}`

Ejemplo básico:

```bash
curl "http://127.0.0.1:8000/stats/torvalds"
```

Ejemplo con personalización:

```bash
curl "http://127.0.0.1:8000/stats/torvalds?card=github&theme=tokyonight&show_avatar=true&bg_color=1a1b27&title_color=70a5fd&text_color=a9b1d6&icon_color=bf91f3"
```

Parámetros soportados:

- `card`: `level`, `level-alternate`, `github`, `contribution-graph`, `top-languages`
- `theme`: `default`, `dark`, `tokyonight`, `radical`, `dracula`, `vision-friendly-dark`, `minimalist`
- `show_avatar`: `true|false`
- `hide_border`: `true|false`
- Colores opcionales: `bg_color`, `title_color`, `text_color`, `icon_color`, `border_color`, `accent_color`

La respuesta se entrega como `image/svg+xml`.

## Fórmula de nivel

Se usa una curva de XP acumulada sobre contribuciones totales:

- `xp = total_contributions_all_time`
- `level = floor(sqrt(xp / level_base_xp)) + 1`
- `progress = avance porcentual hacia el siguiente nivel`

El parámetro `LEVEL_BASE_XP` permite calibrar la dificultad.

## Caché

- TTL por usuario/opciones: `CACHE_TTL_SECONDS` (default `21600`, 6 horas)
- Tamaño máximo de cache: `CACHE_MAX_ENTRIES`
- Clave de caché derivada de username + tema + tipo de tarjeta + opciones visuales

## Despliegue en Railway

1. Crea un nuevo proyecto en Railway desde este repositorio.
2. En variables de entorno agrega:
   - `GITHUB_TOKEN`
   - `ENVIRONMENT=production`
   - `LOG_LEVEL=INFO`
3. Configura:
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Define runtime de Python 3.11+.
5. Deploy.

## Despliegue en Render

1. Crea un **Web Service** en Render conectado al repositorio.
2. Configura:
   - Environment: `Python 3`
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Variables de entorno recomendadas:
   - `GITHUB_TOKEN`
   - `ENVIRONMENT=production`
   - `LOG_LEVEL=INFO`
4. Deploy.

## Observaciones de producción

- Sin token GitHub o con token inválido, GraphQL puede fallar por autenticación/rate limits.
- Para mayor estabilidad, usa token dedicado de solo lectura y rota el secreto periódicamente.
- Si quieres escalar horizontalmente, considera migrar a caché distribuida (Redis) manteniendo la misma interfaz de servicio.
