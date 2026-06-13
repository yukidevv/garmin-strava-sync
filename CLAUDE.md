# CLAUDE.md

Garminのランアクティビティ（タイトル・詳細）の変更を検知し、対応するStravaアクティビティへ反映する個人用ツール。Garminを正とする一方向同期。

# ルール
- 返答は日本語で行うこと
- Conventional Commitsに従うこと (feat:, fix:, chore: など)

## 全体構成
処理本体は**単発Dockerコンテナ**、スケジューリングはホストの systemd timer。

| 要素 | 中身 | 役割 |
|---|---|---|
| `sync` コンテナ | 自作Python(CLI) | Garmin取得→突合せ→Strava更新。1回同期して終了（常駐しない） |
| systemd timer | ホスト | 1時間ごとに `docker compose run --rm sync` を実行 |

- コンテナは実行時のみ起動。アイドル時のリソースはゼロ。
- 同期件数は `.env` の `SYNC_ACTIVITY_COUNT`（既定3）。
- 永続ボリューム: `garmin_token`（Garminログインキャッシュ）。
- 設計変遷: スケジューラに n8n を検討→純cron用途に過剰でsystemd timerへ。
  さらに常駐コンテナ+HTTP(FastAPI `/sync`)も毎時バッチに過剰なため、
  単発コンテナ直実行へ移行（HTTPサーバ撤去）。失敗通知が要れば `.service` の `OnFailure=` で対応。

## 紐付けロジック（重要な設計判断）
- **GarminとStravaは開始時刻(UTC)の一致で紐付ける。** Garmin→Strava自動連携なら
  `startTimeGMT` と `start_date` が秒まで一致する（実データで確認済み）。
- Strava `external_id`（`garmin_ping_<id>`）の数値はGarminの `activityId` とは別物のため**使わない**。
- **Garminを正**とし、タイトル(`name`)・詳細(`description`)に差分がある場合のみStravaを更新（冪等）。
- **Garmin側の詳細が空のときはStravaを上書きしない**（誤って消さない安全側の判断）。

## Strava OAuth
- refresh_tokenは **`activity:read_all` と `activity:write`** スコープが必要。
  `read` だけだと `/athlete/activities` が401、更新も不可。
- 認証情報は `.env` に集約（`STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET` / `STRAVA_REFRESH_TOKEN`）。

## 主要ファイル
- `src/sync.py` … コアロジック（Garmin取得・Strava API・突合せ・差分判定 `compute_payload`・更新）。CLIエントリ `_main`（`SYNC_ACTIVITY_COUNT` を既定件数に）
- `main.py` … ローカル検証用CLI（`src.sync._main` に委譲）
- `tests/test_sync.py` … 突合せキー・差分判定のユニットテスト
- `Dockerfile` / `docker-compose.yml` … sync単発ジョブのイメージとcompose
- `systemd/garmin-strava-sync.{service,timer}` … 1時間ごとに `docker compose run --rm sync` するスケジューラ

## 開発コマンド
```sh
uv sync
uv run python main.py --count 1 --dry-run   # 差分検出のみ（書き込まない）
uv run python main.py --count 3             # 実際に同期
uv run pytest -q                            # テスト
```
Docker:
```sh
docker compose build
docker compose run --rm sync                # 単発同期（systemdと同じ）
```
デプロイ手順（トークンseed・compose build・systemd timer設置）は README.md を参照。
