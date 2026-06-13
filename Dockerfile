FROM python:3.12-slim

# uv をコピー
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# 依存だけ先に入れてレイヤキャッシュを効かせる
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

COPY src ./src

ENV GARMIN_TOKEN_DIR=/data/.garminconnect

# 1回だけ同期して終了する単発ジョブ（常駐しない）。件数は SYNC_ACTIVITY_COUNT。
CMD ["uv", "run", "--no-dev", "python", "-m", "src.sync"]
