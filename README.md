# garmin-strava-sync
garminのアクティビティ(タイトル・詳細)の変更を検知し、対応するstravaアクティビティへ反映するツール。<br>
非常に無意味な私だけのツール。

## CAUTION!!
2026/07/02時点でサブスクライバーではない場合、APIの利用が出来なくなりました

## 概要
garmin側でタイトル・詳細を変更した場合、その内容を検知してstravaへ反映する。
- garminの開発者登録は面倒なので `garmin-connect`(python) を使用
- 処理本体は単発Dockerコンテナ。ホストの systemd timer が1時間ごとに起動して同期
- 差分があればstravaを更新

## 紐付け方法
GarminとStravaのアクティビティは **開始時刻(UTC)の一致** で紐付ける
（Garmin→Strava自動連携なら秒まで一致する）。Garminを正とし、
タイトル(name)・詳細(description)に差分がある場合のみStravaを更新する。
※ Garmin側の詳細が空の場合はStravaを上書きしない（消さない）。

## 構成
| 要素 | 役割 |
|---|---|
| `sync` コンテナ (自作Python) | Garmin取得→突合せ→Strava更新。**単発実行**で1回同期して終了（常駐しない） |
| systemd timer (ホスト) | 1時間ごとに `docker compose run --rm sync` を実行するスケジューラ |

- コンテナは実行時のみ起動するためアイドル時のリソースはゼロ。
- 同期件数は `.env` の `SYNC_ACTIVITY_COUNT`（既定3）。
- 永続ボリューム: `garmin_token`(Garminログインキャッシュ)

## セットアップ
1. `.env` を用意（`.env.example` 参照）
   - Garmin: `GARMIN_EMAIL` / `GARMIN_PASSWORD`
   - Strava: `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET` / `STRAVA_REFRESH_TOKEN`
     - refresh_tokenは **`activity:read_all` と `activity:write`** のスコープが必要
       （`read` だけだとアクティビティ取得・更新ができない）
2. イメージをビルド
   ```sh
   docker compose build
   ```
3. （推奨）Garminのログイントークンをvolumeに事前投入
   - 初回ログインはMFAを求められ得るためヘッドレスで失敗しやすい。
     ローカルでログイン済みの `.garminconnect/` をvolumeへコピーしておくと確実。
     ```sh
     docker volume create garmin-strava-sync_garmin_token
     docker run --rm -v garmin-strava-sync_garmin_token:/data \
       -v "$PWD/.garminconnect":/seed alpine \
       sh -c "mkdir -p /data/.garminconnect && cp -a /seed/. /data/.garminconnect/"
     ```
4. 動作確認（単発実行）
   ```sh
   docker compose run --rm sync
   ```
5. systemd timer を設置（初回のみ・スケジューラ）
   - `.service` の `WorkingDirectory=` をこのリポジトリの配置先に合わせて編集
   ```sh
   sudo cp systemd/garmin-strava-sync.{service,timer} /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now garmin-strava-sync.timer
   ```
   - 状態確認: `systemctl list-timers garmin-strava-sync.timer`
   - 手動実行: `sudo systemctl start garmin-strava-sync.service`（= `docker compose run --rm sync`）
   - ログ: `journalctl -u garmin-strava-sync.service`
   - 失敗通知が欲しくなったら `.service` に `OnFailure=` を足して通知ユニットを呼ぶ

## ローカルでの動作確認
```sh
uv sync
uv run python main.py --count 1 --dry-run   # 差分検出のみ（書き込まない）
uv run python main.py --count 3             # 実際に同期
```

## 今後のTODO / 既知の制限
ローカルで動くプロトタイプとしては完成。本番運用品質には以下が未対応。

- [ ] **実サーバ未デプロイ**: 動作確認はローカルのみ。サーバでの
  トークンseed→`compose build`→systemd timer設置 は手順化済みだが未実行。
- [ ] **Garmin再ログイン(MFA)耐久性が未知**: seedトークンで稼働中。
  トークン失効時の再ログインでMFAを求められるとサーバ上で無言で失敗する恐れ。
  → 長期運用の最大リスク。
- [ ] **失敗通知なし**: 同期失敗時は `journalctl` に残るのみ。アラート未実装。
  （`.service` の `OnFailure=` で通知ユニットを足せば対応可能）
- [ ] **直近N件の外は直らない**: 古い不一致（例: `小山町ラン`↔`朝のランニング`）は
  対象外のまま。`SYNC_ACTIVITY_COUNT` を増やせば対象に入る。
- [x] ~~テストなし~~ → 突合せ/差分判定の純ロジックにユニットテスト追加済み

## 技術
- python3 / garmin-connect
- systemd timer (スケジューラ)
- Docker / docker compose
