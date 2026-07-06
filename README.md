# GitHub Issues → Discord フォーラム通知 Bot

GitHub Issue の作成・編集・クローズ・再オープン、およびコメントを Discord の **フォーラムチャンネル** に通知する GitHub Actions ワークフローです。

**ファイル1つだけ** で完結します。Python も外部サーバーも不要です。

## 仕組み

```
GitHub リポジトリ (ChihaluCoding/stackplus)
  │
  ├─ Issue 作成 ──────→ フォーラムに新規投稿 + Open タグ
  ├─ Issue クローズ ──→ スレッドに通知 + Closed タグ + アーカイブ
  ├─ Issue 再オープン → スレッド復帰 + Open タグ
  ├─ Issue 編集 ──────→ スレッドに通知
  └─ コメント追加 ────→ 同一スレッドに追記
```

Issue ↔ Discord スレッドの紐付けは、Issue 本文末尾に HTML コメント `<!-- discord-thread:ID -->` を埋め込むことで管理します（Markdown 上は見えません）。

## 必要なもの

- Discord Bot（[Developer Portal](https://discord.com/developers/applications) で作成）
- Bot 権限: `Send Messages`, `Manage Threads`, `Read Message History`
- 通知先の **フォーラムチャンネル** とタグ（Open / Closed / Reopened）
- GitHub リポジトリのデフォルト `GITHUB_TOKEN`（PAT 不要）

## セットアップ手順

### 1. Discord Bot を作成

1. <https://discord.com/developers/applications> → **New Application**
2. **Bot** タブ → **Reset Token** → トークンをコピー
3. **OAuth2 → URL Generator** で `bot` を選択
4. 権限: `Send Messages`, `Manage Threads`, `Read Message History`
5. 生成 URL で Bot をサーバーに招待

### 2. フォーラムチャンネルとタグを作成

1. Discord サーバーで **フォーラム** チャンネルを作成
2. タグを 3 つ作成: `Open`, `Closed`, `Reopened`
3. フォーラムの権限で Bot に `送信/スレッド管理` を許可
4. [開発者モード](https://support.discord.com/hc/ja/articles/206343498) を有効化し、ID をコピー:
   - フォーラムチャンネル ID
   - Open / Closed / Reopened タグ ID

### 3. GitHub Secrets を登録

`ChihaluCoding/stackplus` リポジトリの **Settings → Secrets and variables → Actions** で以下を追加:

| Name | Value |
|---|---|
| `DISCORD_BOT_TOKEN` | Bot トークン |
| `DISCORD_FORUM_CHANNEL_ID` | フォーラムチャンネル ID |
| `DISCORD_TAG_OPEN` | Open タグの ID |
| `DISCORD_TAG_CLOSED` | Closed タグの ID |
| `DISCORD_TAG_REOPENED` | Reopened タグの ID |

> `GITHUB_TOKEN` は自動で使われるため Secret 登録不要です。PAT も不要です。

### 4. ワークフローを配置

`.github/workflows/discord-notify.yml` を `ChihaluCoding/stackplus` リポジトリにコミット・プッシュ:

```bash
git add .github/workflows/discord-notify.yml
git commit -m "Add Discord forum notification workflow"
git push
```

### 5. 既存 Issue を一括投稿（バックフィル）

現在ある Issue も全て Discord に投稿したい場合:

1. リポジトリの **Actions** タブ → **Discord Forum Notify**
2. **Run workflow** をクリック
3. `backfill` にチェックが入ったまま **Run workflow** をクリック
4. 全 Issue がフォーラムに投稿される（クローズ済みはアーカイブ状態で作成）

## 通知されるイベント

| イベント | 色 | 動作 |
|---|---|---|
| Issue 作成 | 青 | 新規フォーラム投稿 + `Open` タグ |
| Issue 編集 | 黄 | スレッドに通知 |
| Issue クローズ | 赤 | スレッド通知 + `Closed` タグ + アーカイブ |
| Issue 再オープン | 緑 | スレッド復帰 + `Open` タグ |
| コメント追加/編集/削除 | 緑/黄/赤 | 同一スレッドに追記 |

## ファイル構成

```
.github/
└── workflows/
    └── discord-notify.yml    # これ1つだけ
```

## トラブルシューティング

- **`403 Forbidden`**
  - Bot がフォーラムチャンネルにアクセスできるか確認
  - `Manage Threads` 権限があるか確認
- **コメントがスレッドに追記されない**
  - Issue 本文から `<!-- discord-thread: -->` マーカーが消去されていないか確認
- **バックフィルで一部失敗する**
  - Discord レート制限（2秒/件の待機を入れています）。Issue が多い場合は時間がかかります

## License

MIT