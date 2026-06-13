FROM python:3.12-slim

# uv をコピー
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# 依存だけ先に入れてレイヤキャッシュを効かせる
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

COPY src ./src

ENV GARMIN_TOKEN_DIR=/data/.garminconnect
EXPOSE 8000

CMD ["uv", "run", "--no-dev", "uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8000"]
