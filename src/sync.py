"""Garminのランアクティビティ変更をStravaへ反映するコアロジック。

紐付けは開始時刻(UTC)の一致で行う。Garminを正とし、タイトル(name)と
詳細(description)に差分があればStravaを更新する。
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

import requests
from garminconnect import Garmin

logger = logging.getLogger("sync")

STRAVA_API = "https://www.strava.com/api/v3"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"


@dataclass
class SyncResult:
    garmin_id: int
    name: str
    start_utc: str
    status: str  # updated | unchanged | no_match | error
    strava_id: int | None = None
    changes: list[str] = field(default_factory=list)
    detail: str | None = None

    def as_dict(self) -> dict:
        return {
            "garmin_id": self.garmin_id,
            "name": self.name,
            "start_utc": self.start_utc,
            "status": self.status,
            "strava_id": self.strava_id,
            "changes": self.changes,
            "detail": self.detail,
        }


def _parse_garmin_gmt(value: str) -> datetime:
    # 例: "2026-06-12 22:00:55" (UTC)
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def _parse_strava_date(value: str) -> datetime:
    # 例: "2026-06-12T22:00:55Z"
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def compute_payload(run: dict, strava_detail: dict) -> tuple[dict, list[str]]:
    """Garminを正として、Stravaに送るべき更新内容と変更フィールドを返す。

    純粋関数。外部I/Oを持たないのでここがテスト対象。
    Garmin側が空の値ではStravaを上書きしない（消さない）。
    """
    payload: dict = {}
    changes: list[str] = []
    if run.get("name") and strava_detail.get("name") != run["name"]:
        payload["name"] = run["name"]
        changes.append("name")
    if run.get("description") and (strava_detail.get("description") or "") != run["description"]:
        payload["description"] = run["description"]
        changes.append("description")
    return payload, changes


# --- Garmin ------------------------------------------------------------------

def fetch_garmin_runs(count: int, token_dir: str) -> list[dict]:
    os.makedirs(token_dir, exist_ok=True)
    client = Garmin(os.environ["GARMIN_EMAIL"], os.environ["GARMIN_PASSWORD"])
    client.login(token_dir)
    activities = client.get_activities(0, count)
    runs = []
    for a in activities:
        runs.append({
            "activityId": a.get("activityId"),
            "name": a.get("activityName") or "",
            "description": a.get("description") or "",
            "type": (a.get("activityType") or {}).get("typeKey"),
            "startGMT": a.get("startTimeGMT"),
        })
    return runs


# --- Strava ------------------------------------------------------------------

def strava_access_token() -> str:
    resp = requests.post(STRAVA_TOKEN_URL, data={
        "client_id": os.environ["STRAVA_CLIENT_ID"],
        "client_secret": os.environ["STRAVA_CLIENT_SECRET"],
        "grant_type": "refresh_token",
        "refresh_token": os.environ["STRAVA_REFRESH_TOKEN"],
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]


def fetch_strava_activities(token: str, per_page: int) -> list[dict]:
    resp = requests.get(
        f"{STRAVA_API}/athlete/activities",
        headers={"Authorization": f"Bearer {token}"},
        params={"per_page": per_page},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_strava_detail(token: str, activity_id: int) -> dict:
    resp = requests.get(
        f"{STRAVA_API}/activities/{activity_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def update_strava(token: str, activity_id: int, payload: dict) -> None:
    resp = requests.put(
        f"{STRAVA_API}/activities/{activity_id}",
        headers={"Authorization": f"Bearer {token}"},
        data=payload,
        timeout=30,
    )
    resp.raise_for_status()


# --- Sync --------------------------------------------------------------------

def sync(count: int = 3, token_dir: str | None = None, dry_run: bool = False) -> list[dict]:
    token_dir = token_dir or os.environ.get("GARMIN_TOKEN_DIR", ".garminconnect")

    runs = fetch_garmin_runs(count, token_dir)
    token = strava_access_token()
    # 同じ時間帯を確実にカバーできるよう余裕をもって取得
    strava_list = fetch_strava_activities(token, per_page=max(count * 3, 10))
    strava_by_start = {_parse_strava_date(s["start_date"]): s for s in strava_list}

    results: list[SyncResult] = []
    for run in runs:
        start = _parse_garmin_gmt(run["startGMT"])
        res = SyncResult(
            garmin_id=run["activityId"],
            name=run["name"],
            start_utc=start.isoformat(),
            status="no_match",
        )

        match = strava_by_start.get(start)
        if not match:
            results.append(res)
            logger.info("no match for garmin %s (%s)", run["activityId"], start)
            continue

        res.strava_id = match["id"]
        try:
            detail = fetch_strava_detail(token, match["id"])
            payload, changes = compute_payload(run, detail)
            res.changes = changes

            if not payload:
                res.status = "unchanged"
            elif dry_run:
                res.status = "updated"  # 実際には書かない
                res.detail = "dry_run"
            else:
                update_strava(token, match["id"], payload)
                res.status = "updated"
        except requests.HTTPError as e:
            res.status = "error"
            res.detail = f"{e.response.status_code}: {e.response.text[:200]}"
            logger.exception("strava update failed for %s", match["id"])

        results.append(res)
        logger.info("%s strava=%s changes=%s", res.status, res.strava_id, res.changes)

    return [r.as_dict() for r in results]


def _main() -> None:
    import argparse
    import json

    from dotenv import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser(description="Garmin → Strava sync")
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    results = sync(count=args.count, dry_run=args.dry_run)
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _main()
