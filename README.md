# garmin-strava-sync
garminのアクティビティ(タイトル・詳細)の変更を検知し、対応するstravaアクティビティへ反映するツール。<br>
非常に無意味な私だけのツール。

## 概要
garmin側でタイトル・詳細を変更した場合、その内容を検知してstravaへ反映する。
- garminの開発者登録は面倒なので `garmin-connect`(python) を使用
- n8nで1時間ごとに監視し、差分があればstravaを更新
- 全てDocker(compose)に内包。サーバで `docker compose up -d` 一発で稼働

## 紐付け方法
GarminとStravaのアクティビティは **開始時刻(UTC)の一致** で紐付ける
（Garmin→Strava自動連携なら秒まで一致する）。Garminを正とし、
タイトル(name)・詳細(description)に差分がある場合のみStravaを更新する。
※ Garmin側の詳細が空の場合はStravaを上書きしない（消さない）。

## 構成
| サービス | 役割 |
|---|---|
| `sync` (自作Python) | Garmin取得→突合せ→Strava更新。FastAPI `/sync` を公開 |
| `n8n` (公式image) | 1時間ごとに `/sync` をHTTPで叩くスケジューラ |

永続ボリューム: `garmin_token`(ログインキャッシュ), `n8n_data`(ワークフロー)

## セットアップ
1. `.env` を用意（`.env.example` 参照）
   - Garmin: `GARMIN_EMAIL` / `GARMIN_PASSWORD`
   - Strava: `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET` / `STRAVA_REFRESH_TOKEN`
     - refresh_tokenは **`activity:read_all` と `activity:write`** のスコープが必要
       （`read` だけだとアクティビティ取得・更新ができない）
2. （推奨）Garminのログイントークンをvolumeに事前投入
   - 初回ログインはMFAを求められ得るためヘッドレスで失敗しやすい。
     ローカルでログイン済みの `.garminconnect/` をvolumeへコピーしておくと確実。
     ```sh
     docker compose up -d sync
     docker run --rm -v garmin-strava-sync_garmin_token:/data \
       -v "$PWD/.garminconnect":/seed alpine \
       sh -c "cp -a /seed/. /data/.garminconnect/"
     ```
3. 起動
   ```sh
   docker compose up -d --build
   ```
4. n8nワークフローを取り込む（初回のみ）
   - ブラウザで `http://<server>:5678` を開く
   - `n8n/workflows/garmin-strava-sync.json` をUIからImport → 有効化(Active)
   - もしくは: `docker compose exec n8n n8n import:workflow --input=/workflows/garmin-strava-sync.json`
     （取り込み後、UIでActiveに切り替え）

## ローカルでの動作確認
```sh
uv sync
uv run python main.py --count 1 --dry-run   # 差分検出のみ（書き込まない）
uv run python main.py --count 3             # 実際に同期
```

## 今後のTODO / 既知の制限
ローカルで動くプロトタイプとしては完成。本番運用品質には以下が未対応。

- [ ] **種目フィルタ（要修正）**: 現状は直近N件を種目で絞らず処理する。
  最新がバイク/スイムだとそれも同期対象になる。`type == "running"` で絞るべき。
- [ ] **実サーバ未デプロイ**: 動作確認はローカルのみ。サーバでの
  トークンseed→`up`→ワークフローimport/activate は手順化済みだが未実行。
- [ ] **Garmin再ログイン(MFA)耐久性が未知**: seedトークンで稼働中。
  トークン失効時の再ログインでMFAを求められるとサーバ上で無言で失敗する恐れ。
  → 長期運用の最大リスク。
- [ ] **失敗通知なし**: `/sync` 失敗時はn8nログに残るのみ。アラート未実装。
- [ ] **直近N件の外は直らない**: 古い不一致（例: `小山町ラン`↔`朝のランニング`）は
  対象外のまま。`SYNC_ACTIVITY_COUNT` を増やせば対象に入る。
- [ ] **テストなし**

## 技術
- python3 / FastAPI / garmin-connect
- n8n
- Docker / docker compose
