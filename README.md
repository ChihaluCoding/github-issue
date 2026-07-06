# GitHub Issues → Discord フォーラム通知 Bot

指定した複数リポジトリの Issue / コメントを **GitHub Actions 上で定期ポーリング** して、Discord の **フォーラムチャンネル** に通知する bot です。
外部サーバーは不要です。Python スクリプトを GitHub Actions の `schedule` で定期実行し、状態 (`state.json`) をリポジトリにコミットして次回実行に引き継ぎます。

## 仕組み

```
  ┌───────────────────────────────────────────────────────┐
  │ GitHub Actions (cron: 5 分ごと)                       │
  │                                                       │
  │  1. actions/checkout でリポジトリを取得               │
  │  2. Python スクリプト起動                              │
  │     ・watched-repos.json から監視対象を読込           │
  │     ・state.json の last_run 以降に更新された Issue    │
  │       を各リポジトリごとに取得（PR は除外）           │
  │     ・新規 Issue → Discord フォーラムに新規投稿作成   │
  │     ・既存 Issue の状態変化 → スレッドに通知 + タグ切替 │
  │     ・新規コメント → 同一スレッドに embed で追記       │
  │  3. state.json を git commit & push                   │
  └───────────────────────────────────────────────────────┘
            │
            ▼
   Discord フォーラムチャンネル
```

Issue ↔ Discord スレッドの紐付けは `state.json` 内の `issues` テーブル（キー: `owner/repo#番号`）で管理します。監視対象リポジトリ側には何も変更を加えません。

## 監視できるリポジトリ

- 自分が所有するリポジトリはもちろん、**他人の公開リポジトリ** も監視可能です
- GitHub PAT (`public_repo` または `repo` スコープ) を使ってアクセスします
- 1つのフォーラムチャンネルで複数のリポジトリの Issue を混在して管理できます（スレッド名に `[owner/repo]` プレフィックスが付きます）

## 必要なもの

- Discord Bot（[Developer Portal](https://discord.com/developers/applications) で作成）
- Bot 権限: `Send Messages`, `Manage Threads`, `Read Message History`, `Apply Tags`
- 通知先の **フォーラムチャンネル** と 3 つのタグ（Open / Closed / Reopened）
- GitHub Personal Access Token (PAT) — `public_repo`（公開リポジトリ-only）または `repo`（プライベート含む）スコープ

## セットアップ手順

### 1. Discord Bot を作成してサーバーに招待

1. <https://discord.com/developers/applications> で **New Application** を作成
2. **Bot** タブで **Reset Token** → トークンをコピー
3. **OAuth2 → URL Generator** で `bot` を選択
4. 権限は `Send Messages`, `Manage Threads`, `Read Message History` を指定
5. 生成された URL で Bot をサーバーに招待

### 2. フォーラムチャンネルとタグを作成

1. サーバーで **チャンネル作成** → 種別を **フォーラム** に設定
2. フォーラムにタグを 3 つ作成: `Open`, `Closed`, `Reopened`
3. フォーラムチャンネルの権限設定で Bot を追加し `送信/スレッド管理` を許可
4. [開発者モード](https://support.discord.com/hc/ja/articles/206343498) を有効化し、以下の ID を コピー:
   - フォーラムチャンネル ID
   - `Open`, `Closed`, `Reopened` の各タグ ID

### 3. GitHub パーソナルアクセストークン (PAT) を発行

1. GitHub の **Settings → Developer settings → Personal access tokens → Fine-grained tokens**（または Classic PAT）
2. スコープ `public_repo`（公開のみ）または `repo`（プライベート含む）を付与
3. トークンをコピー

### 4. GitHub リポジトリに Secret を登録

ワークフローを置くリポジトリの **Settings → Secrets and variables → Actions** で以下を追加:

| Secret 名 | 値 |
|---|---|
| `GH_PAT` | GitHub PAT（手順3） |
| `DISCORD_BOT_TOKEN` | Bot トークン（手順1） |
| `DISCORD_FORUM_CHANNEL_ID` | フォーラムチャンネル ID |
| `DISCORD_TAG_OPEN` | Open タグの ID |
| `DISCORD_TAG_CLOSED` | Closed タグの ID |
| `DISCORD_TAG_REOPENED` | Reopened タグの ID |

### 5. 監視対象リポジトリを指定

ルートの `watched-repos.json` を編集:

```json
{
  "repos": [
    "octocat/Hello-World",
    "torvalds/linux",
    "your-name/your-private-repo"
  ]
}
```

### 6. ワークフローを配置して push

```bash
git add .github/workflows/discord-notify.yml \
        scripts/discord_forum_notify.py \
        requirements.txt \
        watched-repos.json
git commit -m "Add Discord forum issue notifier"
git push
```

これで設定完了です。初回 push 時にはワークフローが起動し、`state.json` のベースライン時刻を記録して終了します（通知は送信されません）。次回以降の cron 実行から実際の通知が始まります。

## 監視間隔（カスタマイズ）

`.github/workflows/discord-notify.yml` の `cron` を編集します:

```yaml
schedule:
  - cron: '*/5 * * * *'   # 5 分ごと（既定）
  # - cron: '*/10 * * * *' # 10 分ごと
  # - cron: '*/15 * * * *' # 15 分ごと
  # - cron: '0 * * * *'    # 1 時間ごと
```

GitHub Actions の cron は分単位の最小刻みで、実際の起動は最大 数分 遅れることがあります。

## 通知されるイベント

| イベント | 色 | 動作 |
|---|---|---|
| 新規 Issue 検出 | 青 | フォーラムに新規投稿作成 + `Open` タグ付与 |
| Issue 編集 | 黄 | スレッドに embed 追記 |
| Issue クローズ | 赤 | スレッドに通知 + `Closed` タグ付与 + アーカイブ・ロック |
| Issue 再オープン | 緑 | スレッド復帰 + `Open` タグ付与 + 通知 |
| 新規コメント | 緑 | 同一スレッドに embed 追記 |

> **注**: GitHub API の `since` パラメータで「`last_run` 以降に `updated_at` 更新された Issue」を取得するため、コメントが付いた Issue もまとめて取得されます。コメントは個別に取得して重複を避けてスレッドへ送信します。

## 手動での再取得（バックフィル）

Actions タブから **Run workflow** を実行すると、`since` 入力欄に ISO8601 形式（例: `2026-07-01T00:00:00Z`）で時刻を指定して、その時刻以降の更新を再取得できます。この場合 `state.json` の `last_run` は上書きされません。

## 初回実行の注意

**初回実行時は通知を送信せず、ベースライン時刻だけを `state.json` に記録して終了します。** これは履歴の全 Issue が一斉に Discord に投稿されるのを防ぐためです。
すぐに通知を開始したい場合は、初回実行後に **Run workflow** を手動で起動し、`since` 入力に少し前の時刻を指定してください。

## トラブルシューティング

- **ワークフローが全く起動しない**
  - GitHub Actions の cron は `main` / `master` ブランチに置いたワークフローのみ実行されます
  - リポジトリの Actions タブで「This scheduled workflow is disabled because there hasn't been activity in at least 60 days.」と表示されたら有効化ボタンを押してください
- **`403 Forbidden` や `404 Not Found` でリポジトリ取得に失敗する**
  - PAT のスコープが足りているか（プライベートなら `repo` 必須）
  - リポジトリ名の `owner/repo` のつづりが正しいか確認
- **`DISCORD 403` で forum thread 作成に失敗する**
  - Bot がフォーラムチャンネルにアクセスできる権限か確認
  - `Manage Threads` 権限が不足していないか確認
- **同じコメントが重複して投稿される**
  - `state.json` の `last_comment_id` が正しく更新されていない可能性があります
  - `state.json` を手動編集して該当 Issue の `last_comment_id` を修正するか、該当エントリを削除してください
- **長文の Issue 本文 / コメント本文**
  - 自動的に 4096 字で切り詰められます（Discord Embed description の上限）

## ファイル構成

```
.
├── .github/
│   └── workflows/
│       └── discord-notify.yml       # 定期実行ワークフロー
├── scripts/
│   └── discord_forum_notify.py      # 通知スクリプト本体
├── requirements.txt                 # Python 依存 (requests のみ)
├── watched-repos.json               # 監視対象リポジトリ一覧
├── state.json                       # 実行状態（bot が自動コミット）
└── README.md
```

## License

MIT