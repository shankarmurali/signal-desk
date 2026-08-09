#!/usr/bin/env python3
"""Signal Desk — daily open-source intel brief.

Pulls recent items from the roster's RSS feeds (last N hours), optionally
adds an AI-searched digest via the Anthropic API, and writes a dated
markdown brief plus briefs/latest.md.

Usage:
    python generate_brief.py                  # last 48h, default roster
    python generate_brief.py --window-hours 24
    python generate_brief.py --roster my.json --out briefs/

Optional env:
    ANTHROPIC_API_KEY  — enables the AI-searched digest section
    X_BEARER_TOKEN     — hook for X API integration (see fetch_x_posts)
"""
from __future__ import annotations

import argparse
import calendar
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser

USER_AGENT = "signal-desk/1.0 (+https://github.com/) rss reader"


def load_roster(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)["members"]


def entry_time(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime.fromtimestamp(calendar.timegm(t), tz=timezone.utc)
    return None


def fetch_feed_items(member: dict, since: datetime) -> list[dict]:
    """Fetch one member's RSS feed; return entries newer than `since`.

    Per-feed failures are logged and swallowed — one dead feed must never
    kill the brief.
    """
    url = member.get("rss")
    if not url:
        return []
    try:
        parsed = feedparser.parse(url, agent=USER_AGENT)
        if parsed.bozo and not parsed.entries:
            print(f"  [warn] {member['name']}: feed unreadable ({url})", file=sys.stderr)
            return []
        items = []
        for e in parsed.entries[:10]:
            when = entry_time(e)
            if when is None or when < since:
                continue
            items.append({
                "person": member["name"],
                "beat": member.get("beat", ""),
                "title": (e.get("title") or "(untitled)").strip(),
                "url": e.get("link", ""),
                "when": when,
            })
        return items
    except Exception as exc:  # noqa: BLE001 — resilience over purity here
        print(f"  [warn] {member['name']}: {exc}", file=sys.stderr)
        return []


def fetch_x_posts(member: dict, since: datetime) -> list[dict]:
    """X/Twitter integration point.

    X's API requires a paid bearer token, so this ships as a stub. If you
    have one, set X_BEARER_TOKEN and implement the call here using the
    GET /2/users/:id/tweets endpoint. Keep the same return shape as
    fetch_feed_items so render() needs no changes.
    """
    if not os.environ.get("X_BEARER_TOKEN"):
        return []
    # Implement with your token; left empty deliberately.
    return []


def ai_digest(window_hours: int) -> str:
    """Optional: one AI-searched digest section via the Anthropic API."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return ""
    try:
        import urllib.request

        prompt = (
            f"Search the web for the most significant items from the last {window_hours} hours in: "
            "AI security (prompt injection, agent exploits, model abuse), payment fraud and account "
            "takeover, and AI-related threat intelligence. Respond with 4-6 markdown bullet points, "
            "each: **short headline** — one sentence, then the source URL in parentheses. "
            "Only cite URLs found in your search results."
        )
        body = json.dumps({
            "model": "claude-sonnet-4-6",
            "max_tokens": 1500,
            "messages": [{"role": "user", "content": prompt}],
            "tools": [{"type": "web_search_20250305", "name": "web_search"}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.load(resp)
        text = "\n".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        return text.strip()
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] AI digest skipped: {exc}", file=sys.stderr)
        return ""


def render(items: list[dict], digest: str, window_hours: int) -> str:
    now = datetime.now(timezone.utc)
    lines = [
        f"# Signal Desk — Daily Brief",
        "",
        f"_Generated {now.strftime('%Y-%m-%d %H:%M UTC')} · window: last {window_hours}h · "
        f"{len(items)} roster items_",
        "",
    ]
    if digest:
        lines += ["## Across the wire (AI-searched)", "", digest, ""]
    lines += ["## From the roster", ""]
    if not items:
        lines.append(f"_No roster feed items in the last {window_hours} hours._")
    else:
        by_beat: dict[str, list[dict]] = {}
        for it in sorted(items, key=lambda x: x["when"], reverse=True):
            by_beat.setdefault(it["beat"], []).append(it)
        for beat, beat_items in by_beat.items():
            lines.append(f"### {beat}")
            lines.append("")
            for it in beat_items:
                stamp = it["when"].strftime("%b %d")
                lines.append(f"- **{it['person']}** · {stamp} — [{it['title']}]({it['url']})")
            lines.append("")
    lines += [
        "---",
        "_Built with [Signal Desk](https://github.com/). Roster in `roster.json` — PRs welcome._",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--roster", default="roster.json")
    ap.add_argument("--out", default="briefs")
    ap.add_argument("--window-hours", type=int, default=48)
    ap.add_argument("--no-ai", action="store_true", help="skip the AI-searched digest even if a key is set")
    args = ap.parse_args()

    since = datetime.now(timezone.utc) - timedelta(hours=args.window_hours)
    members = load_roster(args.roster)
    print(f"Fetching feeds for {len(members)} roster members (window: {args.window_hours}h)…")

    items: list[dict] = []
    for m in members:
        items.extend(fetch_feed_items(m, since))
        items.extend(fetch_x_posts(m, since))
        time.sleep(0.2)  # be polite to feed hosts

    digest = "" if args.no_ai else ai_digest(args.window_hours)
    md = render(items, digest, args.window_hours)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    dated = out / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.md"
    dated.write_text(md, encoding="utf-8")
    (out / "latest.md").write_text(md, encoding="utf-8")
    print(f"Wrote {dated} and {out / 'latest.md'} ({len(items)} items).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
