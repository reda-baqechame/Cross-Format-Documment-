# Single-service Railway image.
#
# This keeps the existing two-service deployment files intact, but also supports
# Railway projects that deploy only one service from the repository root.
FROM node:20-bookworm-slim AS web-build

ENV DOCOS_RAILWAY_SINGLE_SERVICE=1 \
    API_PROXY_TARGET=http://127.0.0.1:8000

RUN corepack enable
WORKDIR /repo

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY packages ./packages
COPY apps/web ./apps/web

RUN pnpm install --frozen-lockfile
RUN pnpm --filter @docos/web build

FROM node:20-bookworm-slim AS runner

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-venv \
    python3-pip \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    NODE_ENV=production \
    NODE_OPTIONS="--max-old-space-size=384" \
    HOSTNAME=0.0.0.0 \
    DOCOS_RAILWAY_SINGLE_SERVICE=1 \
    API_PORT=8000 \
    API_PROXY_TARGET=http://127.0.0.1:8000 \
    DATABASE_URL=sqlite:////app/data/docos.db \
    BLOB_BACKEND=local \
    LOCAL_BLOB_DIR=/app/data/blobs

# Bake the deploy revision into the image so /api/health and /api/ready can prove which commit
# is live (the post-merge production smoke gates on this). Railway exposes its provided variables
# — including RAILWAY_GIT_COMMIT_SHA — as Docker build args, so declaring the ARG captures the
# commit at build time. We persist it as SOURCE_COMMIT (a settings fallback) rather than
# re-exporting RAILWAY_GIT_COMMIT_SHA, so a real runtime value from Railway still takes
# precedence. Empty when built outside Railway (e.g. locally), which settings reads as "unknown".
ARG RAILWAY_GIT_COMMIT_SHA=""
ENV SOURCE_COMMIT=${RAILWAY_GIT_COMMIT_SHA}

WORKDIR /app

RUN python3 -m venv /opt/venv
COPY backend/pyproject.toml backend/README.md ./backend/
COPY backend/src ./backend/src
WORKDIR /app/backend
RUN pip install --upgrade pip && pip install ".[anthropic,openai]"

WORKDIR /app
COPY backend ./backend
COPY --from=web-build /repo/apps/web/.next/standalone ./web
COPY --from=web-build /repo/apps/web/.next/static ./web/apps/web/.next/static
COPY scripts/railway-single-service-start.sh ./railway-single-service-start.sh

RUN chmod +x /app/railway-single-service-start.sh \
    && mkdir -p /app/data/blobs \
    && useradd --create-home --uid 10001 app \
    && chown -R app:app /app

# Run as root so a Railway volume mounted at /app/data (which mounts root-owned) is
# writable; the entrypoint fixes ownership of the data dir on boot. Running as root is
# standard for Railway single-service containers and avoids the volume-permission crash
# that kills SQLite/local-blob startup under a non-root user.

EXPOSE 3000

CMD ["/app/railway-single-service-start.sh"]
