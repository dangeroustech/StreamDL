FROM mwader/static-ffmpeg:9.0.2-1 AS ffmpeg

# JS runtime for yt-dlp's YouTube challenge solving (yt-dlp-ejs)
FROM denoland/deno:bin-2.9.8 AS deno

# Builds the venv; uv stays out of the final image
FROM python:3.14-slim-trixie AS build

WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1

RUN pip install --no-cache-dir uv==0.13.5

# Dependencies first, so code changes don't reinstall them
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project --no-editable --no-cache

COPY streamdl ./streamdl
RUN uv sync --frozen --no-dev --no-editable --no-cache

FROM python:3.14-slim-trixie

# gosu drops to PUID/PGID; tini reaps orphaned post-script children as PID 1;
# tzdata makes TZ work for recording filenames
RUN apt-get update && \
    apt-get install -y --no-install-recommends gosu tini tzdata ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY --from=deno /deno /usr/local/bin/deno
COPY --from=ffmpeg /ffmpeg /ffprobe /usr/local/bin/

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=build /app/.venv /app/.venv

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD ["/app/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/health', timeout=5)"]

ENTRYPOINT ["/usr/bin/tini", "--", "/app/entrypoint.sh"]
