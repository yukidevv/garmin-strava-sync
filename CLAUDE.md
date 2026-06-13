# CLAUDE.md

Garminのランアクティビティ（タイトル・詳細）の変更を検知し、対応するStravaアクティビティへ反映する個人用ツール。Garminを正とする一方向同期。

## 全体構成
処理本体はDockerコンテナ、スケジューリングはホストの systemd timer。

| 要素 | 中身 | 役割 |
|---|---|---|
| `sync` コンテナ | 自作Python(FastAPI) | Garmin取得→突合せ→Strava更新。`POST /sync` / `GET /health` を `127.0.0.1:8787` に公開 |
| systemd timer | ホスト | 1時間ごとに `curl -X POST http://127.0.0.1:8787/sync` を実行 |

- `/sync` は認証なしのため **localhost限定公開**。
- 永続ボリューム: `garmin_token`（Garminログインキャッシュ）。
- スケジューラに n8n を使う案も検討したが、純粋なcron用途にはオーバースペックなため
  systemd timer に置き換えた（失敗通知が要れば `.service` の `OnFailure=` で対応）。

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
- `src/sync.py` … コアロジック（Garmin取得・Strava API・突合せ・差分判定 `compute_payload`・更新）。CLIエントリ `_main` も持つ
- `src/server.py` … FastAPIアプリ（`/sync`, `/health`）
- `main.py` … ローカル検証用CLI（`src.sync._main` に委譲）
- `tests/test_sync.py` … 突合せキー・差分判定のユニットテスト
- `Dockerfile` / `docker-compose.yml` … syncイメージとcompose（sync単体）
- `systemd/garmin-strava-sync.{service,timer}` … 1時間ごとに `/sync` を叩くスケジューラ

## 開発コマンド
```sh
uv sync
uv run python main.py --count 1 --dry-run   # 差分検出のみ（書き込まない）
uv run python main.py --count 3             # 実際に同期
uv run pytest -q                            # テスト
```
Docker:
```sh
docker compose up -d --build
curl -X POST http://127.0.0.1:8787/sync     # 手動トリガ（systemdと同じ）
```
デプロイ手順（トークンseed・compose up・systemd timer設置）は README.md を参照。

## 状態と既知の制限
ローカルで本番経路（systemd相当のhost curl→sync→Strava更新）まで実動確認済み。
ただし本番運用品質には未到達。未対応項目（種目フィルタ未実装・実サーバ未デプロイ・
MFA耐久性・失敗通知なし 等）は README.md の「今後のTODO / 既知の制限」を参照。
