"""定期トリガ(ホストの systemd timer)から叩かれる同期用HTTPサーバ。"""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI

from .sync import sync

# ローカル実行用。Docker では env_file で注入されるので .env が無くても無害。
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("server")

app = FastAPI(title="garmin-strava-sync")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/sync")
def run_sync() -> dict:
    count = int(os.environ.get("SYNC_ACTIVITY_COUNT", "3"))
    results = sync(count=count)
    updated = [r for r in results if r["status"] == "updated"]
    logger.info("sync done: %d activities, %d updated", len(results), len(updated))
    return {
        "count": len(results),
        "updated": len(updated),
        "results": results,
    }
