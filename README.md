# garmin-strava-sync
garminのアクティビティとstravaのアクティビティを同期させるツール
非常に無意味な私だけのツール

## 概要
garmin側でタイトル、詳細を変更した場合、その内容を検知しstravaへ登録を行う。
- garminの開発者登録は難しいのでgarmin-connectを使用
- n8nで定期的に監視し、変更があった場合、情報を読み取りstravaへ登録を行う

## 技術
- n8n
- garmin-connect(python)
