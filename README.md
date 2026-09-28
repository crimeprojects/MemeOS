# MemeOS

MemeOS is a local-first trading review system for turning wallet activity, chart snapshots, trader notes, and AI analysis into a repeatable feedback loop.

> **Status:** early MVP. The current build is for one trader on one local machine. It is not financial advice and it has no trade execution or wallet-signing capability.

## Current MVP loop

```text
Take a terminal snapshot
  → local watcher detects the PNG
  → read-only wallet activity pull
  → raw activity stored locally
  → candidate trade appears in the dashboard
  → trader reviews the trade
  → end-of-day summary and pattern memory
```

The public repository contains code, tests, architecture, and product direction. Personal wallet data, screenshots, databases, credentials, and private journal content stay local and are gitignored.

## Run locally

From the repository root:

```bash
python3 -m app.dashboard_server --port 8765
```

Open `http://127.0.0.1:8765`.

Run the snapshot watcher separately:

```bash
export MEMEOS_WALLET="YOUR_PUBLIC_WALLET"
python3 -m app.snapshot_watcher
```

The watcher is local collection only. It does not call AI, write to Notion, execute trades, sign transactions, or delete screenshots.

## Test

```bash
python3 -m unittest discover -s tests -v
```

## Data boundaries

- Raw activity and local review state use SQLite under `data/`.
- Terminal screenshots remain outside the repository in the configured Downloads folder.
- API credentials are read from local configuration and never belong in this repository.
- Unmatched/open activity is kept for review and excluded from P&L.
- AI is intended for end-of-session synthesis, not for collection or execution.

## Roadmap

1. Persist candidate positions and local review records.
2. Import an explicit session window from the read-only wallet API.
3. Resolve screenshots to the correct market/trade without guessing.
4. Generate end-of-day summaries and approved trader-profile updates.
5. Add optional multi-user infrastructure only if the single-user workflow proves useful.
