#!/usr/bin/env python3
"""watched-repos.json に指定したリポジトリの Issue / コメントを定期取得し、
Discord フォーラムチャンネルへ通知するスクリプト。

GitHub ペイロードのリアルタイム性はなく、GitHub Actions の schedule で
定期的に起動して GitHub REST API をポーリングする方式（サーバー不要）。

必要な環境変数:
  GH_TOKEN                 GitHub PAT（repos/public_repo スコープ）
  DISCORD_BOT_TOKEN        Discord Bot トークン
  DISCORD_FORUM_CHANNEL_ID 通知先フォーラムチャンネル ID
  DISCORD_TAG_OPEN         Open タグ ID（空欄可）
  DISCORD_TAG_CLOSED       Closed タグ ID（空欄可）
  DISCORD_TAG_REOPENED     Reopened タグ ID（空欄可）
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

import requests

REPOS_FILE = Path("watched-repos.json")
STATE_FILE = Path("state.json")

GH_TOKEN = os.environ.get("GH_TOKEN", "").strip()
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
FORUM_CHANNEL_ID = os.environ.get("DISCORD_FORUM_CHANNEL_ID", "").strip()
TAG_OPEN = os.environ.get("DISCORD_TAG_OPEN", "").strip()
TAG_CLOSED = os.environ.get("DISCORD_TAG_CLOSED", "").strip()
TAG_REOPENED = os.environ.get("DISCORD_TAG_REOPENED", "").strip()

GH_API = "https://api.github.com"
DISCORD_API = "https://discord.com/api/v10"

# Discord Embed 色（10 進数）
COLOR_NEW = 3447003       # 0x3498DB
COLOR_OPEN = 3066993      # 0x2ECC71
COLOR_CLOSED = 10038562  # 0x992D22
COLOR_REOPENED = 3066993  # 0x2ECC71
COLOR_EDITED = 15844367  # 0xF1C40F
COLOR_DELETED = 10038562  # 0x992D22
COLOR_COMMENT = 3066993   # 0x2ECC71

GH_HEADERS = {
    "Authorization": f"Bearer {GH_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
DISCORD_HEADERS = {
    "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
    "Content-Type": "application/json",
}


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_repos() -> list[str]:
    if not REPOS_FILE.exists():
        print(f"[warn] {REPOS_FILE} が見つかりません。空リストで続行します。")
        return []
    try:
        data = json.loads(REPOS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[error] {REPOS_FILE} の JSON が壊れています: {exc}", file=sys.stderr)
        sys.exit(1)
    repos = data.get("repos", []) if isinstance(data, dict) else []
    return [r.strip() for r in repos if r and r.strip()]


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"issues": {}, "last_run": None}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"[warn] {STATE_FILE} が壊れていたのでリセットします。")
        return {"issues": {}, "last_run": None}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def make_embed(color: int, title: str, desc: str, url: str, footer: str) -> dict:
    return {
        "title": (title or "")[:256],
        "description": (desc or "")[:4096],
        "url": url,
        "color": int(color),
        "footer": {"text": (footer or "")[:2048]},
        "timestamp": now_iso(),
    }


def create_forum_thread(name: str, summary: str, embed: dict, tag_id: str) -> str:
    payload = {
        "name": name[:100],
        "auto_archive_duration": 1440,
        "message": {"content": summary[:2000], "embeds": [embed]},
        "applied_tags": [tag_id] if tag_id else [],
    }
    r = requests.post(
        f"{DISCORD_API}/channels/{FORUM_CHANNEL_ID}/threads",
        headers=DISCORD_HEADERS,
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return str(r.json()["id"])


def send_thread_message(thread_id: str, embed: dict) -> None:
    r = requests.post(
        f"{DISCORD_API}/channels/{thread_id}/messages",
        headers=DISCORD_HEADERS,
        json={"embeds": [embed]},
        timeout=30,
    )
    r.raise_for_status()


def update_thread(
    thread_id: str,
    *,
    tags: list[str] | None = None,
    archived: bool | None = None,
    locked: bool | None = None,
) -> None:
    payload: dict = {}
    if tags is not None:
        payload["applied_tags"] = tags
    if archived is not None:
        payload["archived"] = archived
    if locked is not None:
        payload["locked"] = locked
    if not payload:
        return
    r = requests.patch(
        f"{DISCORD_API}/channels/{thread_id}",
        headers=DISCORD_HEADERS,
        json=payload,
        timeout=30,
    )
    r.raise_for_status()


def fetch_issues(repo: str, since_iso: str | None) -> list[dict]:
    params = {
        "state": "all",
        "sort": "updated",
        "direction": "asc",
        "per_page": 100,
    }
    if since_iso:
        params["since"] = since_iso
    r = requests.get(
        f"{GH_API}/repos/{repo}/issues",
        headers=GH_HEADERS,
        params=params,
        timeout=30,
    )
    if r.status_code == 404:
        print(f"  [warn] リポジトリが見つかりません（トークンの権限確認）: {repo}")
        return []
    if r.status_code == 403 and "rate limit" in r.text.lower():
        print(f"  [warn] GitHub API レート制限: {repo} をスキップ")
        return []
    r.raise_for_status()
    items = r.json()
    return [i for i in items if "pull_request" not in i]


def fetch_comments(repo: str, number: int, since_iso: str | None) -> list[dict]:
    params = {"per_page": 100}
    if since_iso:
        params["since"] = since_iso
    r = requests.get(
        f"{GH_API}/repos/{repo}/issues/{number}/comments",
        headers=GH_HEADERS,
        params=params,
        timeout=30,
    )
    if r.status_code == 404:
        return []
    r.raise_for_status()
    return r.json()


def tag_for_state(state: str) -> str:
    if state == "closed":
        return TAG_CLOSED
    if state == "open":
        return TAG_OPEN
    return TAG_REOPENED


def process_repo(repo: str, state: dict, last_run: str) -> None:
    print(f"\n=== {repo} ===")
    issues = fetch_issues(repo, last_run)
    print(f"  取得件数: {len(issues)}")
    for issue in issues:
        number = issue["number"]
        key = f"{repo}#{number}"
        issue_state = issue["state"]
        title = issue["title"]
        body = issue.get("body") or "(本文なし)"
        url = issue["html_url"]
        author = issue["user"]["login"] if issue.get("user") else "unknown"

        prev = state["issues"].get(key)
        if prev is None or "thread_id" not in prev:
            embed = make_embed(
                COLOR_NEW,
                f"🆕 {repo} Issue #{number}: {title}",
                body,
                url,
                f"state: {issue_state} • by @{author}",
            )
            summary = f"Issue #{number} in `{repo}` by @{author}\n{url}"
            thread_name = f"[{repo}] #{number} {title}"
            try:
                thread_id = create_forum_thread(thread_name, summary, embed, tag_for_state(issue_state))
            except requests.HTTPError as exc:
                print(f"  [error] スレッド作成失敗 #{number}: {exc}")
                continue
            state["issues"][key] = {
                "thread_id": thread_id,
                "last_comment_id": 0,
                "state": issue_state,
            }
            # 過去コメントの最大IDを取得して、過去分をスパムしないようにする
            existing_comments = fetch_comments(repo, number, None)
            max_comment_id = max((c["id"] for c in existing_comments), default=0)
            state["issues"][key]["last_comment_id"] = max_comment_id
            print(f"  スレッド作成 #{number} -> thread {thread_id} (過去コメント {len(existing_comments)}件をスキップ)")
            # 既にクローズ済みのIssueならスレッドをアーカイブ
            if issue_state == "closed":
                try:
                    update_thread(
                        thread_id,
                        tags=[TAG_CLOSED] if TAG_CLOSED else None,
                        archived=True,
                        locked=True,
                    )
                    print(f"  #{number} 既存のクローズ済みIssueのためスレッドをアーカイブ")
                except requests.HTTPError as exc:
                    print(f"  [warn] #{number} アーカイブ失敗: {exc}")
            prev = state["issues"][key]
        else:
            thread_id = prev["thread_id"]
            if prev.get("state") != issue_state:
                if issue_state == "closed":
                    embed = make_embed(
                        COLOR_CLOSED,
                        f"🔒 {repo} Issue #{number}: クローズされました",
                        body,
                        url,
                        f"state: closed • by @{author}",
                    )
                    send_thread_message(thread_id, embed)
                    update_thread(
                        thread_id,
                        tags=[TAG_CLOSED] if TAG_CLOSED else None,
                        archived=True,
                        locked=True,
                    )
                    print(f"  #{number} クローズ通知 + スレッドアーカイブ")
                elif issue_state == "open" and prev.get("state") == "closed":
                    embed = make_embed(
                        COLOR_REOPENED,
                        f"♻️ {repo} Issue #{number}: 再オープンされました",
                        body,
                        url,
                        f"state: open • by @{author}",
                    )
                    send_thread_message(thread_id, embed)
                    update_thread(
                        thread_id,
                        tags=[TAG_OPEN] if TAG_OPEN else None,
                        archived=False,
                        locked=False,
                    )
                    print(f"  #{number} 再オープン通知 + スレッド復帰")
                elif issue_state == "open":
                    embed = make_embed(
                        COLOR_EDITED,
                        f"✏️ {repo} Issue #{number}: 編集されました",
                        body,
                        url,
                        f"state: open • by @{author}",
                    )
                    send_thread_message(thread_id, embed)
                    update_thread(
                        thread_id,
                        tags=[TAG_OPEN] if TAG_OPEN else None,
                    )
                    print(f"  #{number} 編集通知")
                prev["state"] = issue_state

        comments = fetch_comments(repo, number, last_run)
        comments = [c for c in comments if c["id"] > prev.get("last_comment_id", 0)]
        comments.sort(key=lambda c: c["id"])
        for c in comments:
            cbody = c.get("body") or "(本文なし)"
            curl = c["html_url"]
            cauthor = c["user"]["login"] if c.get("user") else "unknown"
            cembed = make_embed(
                COLOR_COMMENT,
                f"💬 {repo} #{number} コメント by @{cauthor}",
                cbody,
                curl,
                f"state: {issue_state}",
            )
            try:
                send_thread_message(thread_id, cembed)
            except requests.HTTPError as exc:
                print(f"  [error] コメント送信失敗 #{number}: {exc}")
                break
            prev["last_comment_id"] = c["id"]
            print(f"  #{number} コメント {c['id']} をスレッドへ投稿")


def main() -> int:
    parser = argparse.ArgumentParser(description="Discord forum issue notifier")
    parser.add_argument(
        "--since",
        default=None,
        help="ISO8601 形式で開始時刻を上書き指定（指定時刻以降の更新を再取得）",
    )
    args = parser.parse_args()

    missing = [
        name
        for name, value in [
            ("GH_TOKEN", GH_TOKEN),
            ("DISCORD_BOT_TOKEN", DISCORD_BOT_TOKEN),
            ("DISCORD_FORUM_CHANNEL_ID", FORUM_CHANNEL_ID),
        ]
        if not value
    ]
    if missing:
        print(f"ERROR: 必須環境変数が未設定: {', '.join(missing)}", file=sys.stderr)
        return 1

    repos = load_repos()
    if not repos:
        print("watched-repos.json に監視対象リポジトリが指定されていません。")
        return 0

    state = load_state()
    last_run = args.since or state.get("last_run")
    new_run_time = now_iso()

    if last_run is None:
        print("初回実行です。既存のIssueを全て取得してDiscordに投稿します（過去コメントはスキップ）。")
        last_run = None
    else:
        if args.since:
            print(f"--since によりベースラインを上書き: {last_run}")

    print(f"前回実行時刻: {last_run}")
    try:
        for repo in repos:
            try:
                process_repo(repo, state, last_run)
            except requests.RequestException as exc:
                print(f"[error] {repo} の処理中に例外: {exc}", file=sys.stderr)
    finally:
        if not args.since:
            state["last_run"] = new_run_time
            save_state(state)
            print(f"\n状態を保存しました。次回のベースライン: {new_run_time}")
        else:
            save_state(state)
            print("\n状態を保存しました（last_run は更新しません）")
    return 0


if __name__ == "__main__":
    sys.exit(main())