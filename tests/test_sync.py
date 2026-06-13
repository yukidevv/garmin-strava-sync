"""純ロジック（突合せキー・差分判定）のユニットテスト。

Garmin/Strava への通信は伴わない。データを書き換える判定部分を守るのが目的。
"""
from src.sync import _parse_garmin_gmt, _parse_strava_date, compute_payload


# --- 突合せキー（開始時刻） ---------------------------------------------------

def test_garmin_gmt_matches_strava_date():
    # Garmin "YYYY-MM-DD HH:MM:SS"(UTC) と Strava "...Z" が同一時刻なら一致する
    g = _parse_garmin_gmt("2026-06-12 22:00:55")
    s = _parse_strava_date("2026-06-12T22:00:55Z")
    assert g == s


def test_different_seconds_do_not_match():
    g = _parse_garmin_gmt("2026-06-12 22:00:55")
    s = _parse_strava_date("2026-06-12T22:00:56Z")
    assert g != s


# --- 差分判定（compute_payload） ---------------------------------------------

def test_name_only_change():
    run = {"name": "新タイトル", "description": "同じ本文"}
    detail = {"name": "旧タイトル", "description": "同じ本文"}
    payload, changes = compute_payload(run, detail)
    assert payload == {"name": "新タイトル"}
    assert changes == ["name"]


def test_name_and_description_change():
    run = {"name": "新", "description": "新本文"}
    detail = {"name": "旧", "description": "旧本文"}
    payload, changes = compute_payload(run, detail)
    assert payload == {"name": "新", "description": "新本文"}
    assert changes == ["name", "description"]


def test_no_change_when_equal():
    run = {"name": "同じ", "description": "同じ"}
    detail = {"name": "同じ", "description": "同じ"}
    payload, changes = compute_payload(run, detail)
    assert payload == {}
    assert changes == []


def test_empty_garmin_description_does_not_overwrite():
    # Garmin詳細が空なら、Strava側に本文があっても消さない
    run = {"name": "タイトル", "description": ""}
    detail = {"name": "タイトル", "description": "Stravaの既存本文"}
    payload, changes = compute_payload(run, detail)
    assert payload == {}
    assert changes == []


def test_strava_missing_description_field():
    # StravaのdescriptionがNone/未設定でも、Garminに本文があれば設定する
    run = {"name": "タイトル", "description": "本文"}
    detail = {"name": "タイトル", "description": None}
    payload, changes = compute_payload(run, detail)
    assert payload == {"description": "本文"}
    assert changes == ["description"]
