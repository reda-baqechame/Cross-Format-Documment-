FROM python:3.12-slim

# System deps: Tesseract (with English data) for OCR, libGL for image/PDF libs.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install production dependencies (no dev/test extras; include the Anthropic provider
# so AI editing works when LLM_PROVIDER=anthropic). Copy metadata first for caching.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install ".[anthropic]"

# Application code + migrations + entrypoint.
COPY . .
RUN chmod +x docker-entrypoint.sh

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app

EXPOSE 8000
ENV PORT=8000
ENTRYPOINT ["./docker-entrypoint.sh"]
