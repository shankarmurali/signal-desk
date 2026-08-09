# Signal Desk

A daily open-source intelligence brief for people working in **AI security, payment fraud, threat intel, and trust & safety** — generated automatically every morning by GitHub Actions and committed to this repo.

Each brief pulls the last 48 hours of output from a curated roster of researchers and practitioners (via their RSS feeds), optionally layers in an AI-searched digest of the wider news, and publishes everything as markdown with links: [`briefs/latest.md`](briefs/latest.md).

## Why RSS-first

X/Twitter's API is paid and scraping it is unreliable, so this project deliberately builds on what's stable: most substantive security writing lands on blogs with RSS feeds, which are free, legal, and don't break. An X API hook (`fetch_x_posts` in `generate_brief.py`) is stubbed out for anyone with a bearer token.

## How it works

```
roster.json  ──►  generate_brief.py  ──►  briefs/YYYY-MM-DD.md
  (people,          RSS fetch (48h)          + briefs/latest.md
   feeds)           + optional AI digest
                    via Anthropic API
                          ▲
             .github/workflows/daily-brief.yml
                 (cron, 13:30 UTC daily)
```

## Setup

1. **Fork or clone** this repo and push it to your GitHub account.
2. That's it for the basic version — the Action runs daily and commits the brief. Run it manually anytime from the Actions tab (`workflow_dispatch`).
3. **Optional AI digest:** add an `ANTHROPIC_API_KEY` secret in *Settings → Secrets and variables → Actions* to enable the "Across the wire" section, which runs web searches for the day's most significant items beyond the roster.

Run locally:

```bash
pip install -r requirements.txt
python generate_brief.py --window-hours 48
```

## Customize the roster

All people live in [`roster.json`](roster.json) — no code changes needed. Each member:

```json
{
  "name": "…", "org": "…", "beat": "…",
  "why": "one line on why they're worth following",
  "rss": "https://…/feed/",   // optional — enables daily pull
  "site": "…", "x": "…"        // reference links
}
```

Members without an `rss` entry still appear in the roster but only surface via the AI digest. PRs adding voices (with a one-line `why`) are welcome.

## Extending

- **X/Twitter**: implement `fetch_x_posts()` with your bearer token — the return shape matches the RSS path, so rendering needs no changes.
- **Delivery**: pipe `briefs/latest.md` into email or Slack with one more workflow step (e.g. a `curl` to a Slack webhook).
- **New beats**: beats are just strings in `roster.json`; the brief groups by whatever it finds.

## Design principles

- One dead feed never kills the brief (per-feed failures are logged and skipped).
- Data (roster) is separate from code, so contributions are one-line JSON edits.
- Everything the pipeline produces is plain markdown committed to git — the history *is* the archive.

## License

MIT — see [LICENSE](LICENSE).
