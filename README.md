# GitHub Issues → Discord フォーラム通知 Bot

GitHub Issue を Discord の **フォーラムチャンネル** に投稿として管理する GitHub Actions ワークフローです。
Issue ごとにフォーラム内のスレッド（投稿）を作成し、コメント・状態変更を同じスレッドに集約します。

## 仕組み

1. GitHub で Issue / コメント イベントが発生
2. `.github/workflows/discord-notify.yml` が起動
3. Discord Bot トークンを使って Discord REST API を呼び出し:
   - **Issue 作成**: フォーラムチャンネルに新規投稿（スレッド）を作成し、Issue 本文に隠しマーカー `<!-- discord-thread:ID -->` を埋め込んで紐付け
   - **コメント / 状態変更**: Issue 本文から `thread_id` を読み取り、該当スレッドへ embed で追記
   - **クローズ**: 該当スレッドに状態タグを切り替え、スレッドをアーカイブ

## 必要なもの

- Discord Bot（[Developer Portal](https://discord.com/developers/applications) で作成）
- Bot 権限: `Send Messages`, `Manage Threads`, `Read Message History`, `Apply Tags`（数値権限 `68672` でカバー可）
- 通知先の **フォーラムチャンネル**（フィーチャーが有効なサーバーに作成可能）
- フォーラムに「Open / Closed / Reopened」のタグを事前に作成

## セットアップ手順

### 1. Discord Bot を作成してサーバーに招待

1. <https://discord.com/developers/applications> で **New Application** を作成
2. **Bot** タブで **Reset Token** → トークンをコピー（後で Secret に使う）
3. **OAuth2 → URL Generator** で `bot` と `applications.commands` を選択
4. 権限（Bot Permissions）は `Send Messages`, `Manage Threads`, `Read Message History` を含める
5. 生成された URL で Bot をサーバーに招待

### 2. フォーラムチャンネルを作成し、Bot にアクセス権を付与

1. サーバーの **チャンネル作成** → 種別を **フォーラム** に設定
2. フォーラムにタグを3つ作成（例: `Open` / `Closed` / `Reopened`）
3. フォーラムチャンネルの権限設定で Bot を追加し `送信/スレッド管理` を許可

### 3. 必要な ID を取得

- **チャンネル ID**: フォーラムチャンネル右クリック → ID をコピー（[開発者モード](https://support.discord.com/hc/ja/articles/206343498) を有効化）
- **タグ ID**: フォーラム設定で各タグを右クリック → ID をコピー
  - `Open` タグのID
  - `Closed` タグのID
  - `Reopened` タグのID

### 4. GitHub リポジトリに Secret を登録

リポジトリの **Settings** → **Secrets and variables** → **Actions** で以下を追加:

| Secret 名 | 値 |
|---|---|
| `DISCORD_BOT_TOKEN` | Bot トークン |
| `DISCORD_FORUM_CHANNEL_ID` | フォーラムチャンネルの ID |
| `DISCORD_TAG_OPEN` | Open タグの ID |
| `DISCORD_TAG_CLOSED` | Closed タグの ID |
| `DISCORD_TAG_REOPENED` | Reopened タグの ID |

### 5. ワークフローを配置

```bash
git add .github/workflows/discord-notify.yml
git commit -m "Add Discord forum notification workflow"
git push
```

## 通知されるイベント

| イベント | 色 | タグ | 動作 |
|---|---|---|---|
| Issue 作成 | 青 | Open | 新規フォーラム投稿を作成 |
| Issue 編集 | 黄 | Reopened | スレッドに edit 通知 |
| Issue クローズ | 赤 | Closed | スレッドに通知 + アーカイブ |
| Issue 再オープン | 緑 | Open | スレッドに通知 + タグ切替 |
| コメント追加 | 緑 | — | スレッドに embed 追記 |
| コメント編集 | 黄 | — | スレッドに embed 追記 |
| コメント削除 | 赤 | — | スレッドに embed 追記 |

## Issue ↔ Discord Thread の紐付け

- Issue 作成時に、GitHub Issue の本文末尾に HTML コメントとして `<!-- discord-thread:1234567890 -->` を自動挿入
- Markdown 上は見えませんが、Issue 本文を「Raw」で表示すると確認できます
- GitHub Edit 時に意図的に消さない限り残ります

## 動作確認

1. Issue を新規作成
2. **Actions** タブで `Notify Discord Forum on Issue` を確認
3. Discord フォーラムに投稿が作成されることを確認
4. 当該 Issue にコメントを書き、同じ Discord 投稿に embed が追記されることを確認

## トラブルシューティング

- **`403 Forbidden` になる**
  - Bot がフォーラムチャンネルにアクセスできる権限か確認
  - `Manage Threads` 権限が不足していないか確認
- **タグが付与されない**
  - タグ ID が正しいか、Bot に `Manage Threads` 権限があるか再確認
- **新規スレッドは作られるのにコメントが追記されない**
  - Issue 本文から `<!-- discord-thread: -->` マーカーが消去されていないか確認
- **長文の Issue 本文**
  - Discord Embed description の上限（4096字）に合わせ自動切り詰めします

## ファイル構成

```
.github/
└── workflows/
    └── discord-notify.yml
README.md
```