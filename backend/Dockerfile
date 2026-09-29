# Pinned so Dependabot's docker updates bump uv along with the base image.
FROM ghcr.io/astral-sh/uv:0.12.20 AS uv

FROM python:3.14-slim

COPY --from=uv /uv /bin/uv

WORKDIR /app

# Install system dependencies for OpenCV
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install the locked runtime dependencies into /app/.venv with the image's
# Python, before copying the code so this layer is reused across code changes.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-cache

# CI smoke-tests this image through scripts/validate_docker.sh.
COPY . .

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
