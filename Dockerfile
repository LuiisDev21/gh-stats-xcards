# GitHub Stats xCards — FastAPI + uvicorn
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app
COPY templates ./templates
COPY static ./static
COPY runtime.txt .

EXPOSE 8000

CMD uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
