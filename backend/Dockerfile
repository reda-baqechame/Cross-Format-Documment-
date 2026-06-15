FROM python:3.12-slim

# System deps for document/OCR libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for layer caching
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -e ".[dev]"

COPY . .

EXPOSE 8000
CMD ["uvicorn", "docos.main:app", "--host", "0.0.0.0", "--port", "8000"]
