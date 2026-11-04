# FADE MACHINE — notes for Claude

NFL betting analytics app built in Streamlit. Analytics tool first: odds boards,
ATS/matchup trends from real historical results, fantasy rankings and a mock
draft, and play-money bets paid in "Steel" (not real money).

The owner often works from the Claude mobile app, so keep replies short, explain
changes in plain English, and finish each task with a commit on a branch plus a
PR they can merge from their phone.

## Run and check

```bash
pip install -r requirements.txt
python -m streamlit run app.py          # serves on :8501
python -m py_compile *.py scripts/*.py  # fast syntax check; there is no test suite
```

`main` is deployed to Streamlit Community Cloud — merging to `main` updates the
live app. Never push straight to `main`; open a PR.

## Secrets

Read through `st.secrets` (from `.streamlit/secrets.toml`, which is gitignored),
not environment variables:

- `ODDS_API_KEY` — The Odds API (live lines, props, final scores)
- `SUPABASE_URL`, `SUPABASE_ANON_KEY` — historical games, accounts, durable bets
- `SUPABASE_KEY` — used only by `scripts/load_historical_data.py`
- `POST_STUDIO_PASSCODE` — unlocks the private Post Studio at `?studio=1`
- `ANTHROPIC_API_KEY` — optional Claude drafting in the Post Studio
- `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET` — post to @Fade_Machine

Every one is optional. Without them the app still runs on sample data and shows
an info banner, which is the normal state in a cloud session. Never commit keys,
and never hard-code a fallback key.

## Layout

| File | What it owns |
|---|---|
| `app.py` | Page setup, theme CSS, odds board, tabs, Steel balance/bet placement. Large — grep for the function you need rather than reading it whole. |
| `matchup_trends.py` | Game/matchup ATS trends from the Supabase `games` table |
| `bet_store.py` | SQLite ledger (`bets.db`) for guest bets |
| `user_data.py` | Routes bet reads/writes: signed in → Supabase, guest → SQLite |
| `auth_store.py`, `auth_ui.py` | Optional Supabase sign-in, cookie-backed sessions |
| `bet_settlement.py` | Settles open bets from The Odds API `/scores` |
| `bet_slips.py` | Groups repeat bets into slips; the My Bets tab |
| `bet_analytics.py` | Bet history and trend charts on the Profile tab |
| `content_engine.py` | Headlines, leaderboards and movers derived from the data |
| `cbb_data.py` | College basketball: ESPN scoreboard fetch (no key, no Odds API credits) and the MACHINE ratings model |
| `cbb_edges.py` | Editable list of CBB edges flagged on the ratings and March Madness cheat sheet |
| `cbb_tab.py` | College Hoops tab: board, power ratings, team lookup, March Madness |
| `post_studio.py` | Private `?studio=1` page: picks → X drafts, pick-card image, post |
| `x_poster.py` | X API v2 posting (OAuth 1.0a) and image upload |
| `fantasy_models.py`, `mock_draft.py` | Fantasy rankings and the mock-draft hub |
| `db/*.sql` | Supabase schema — run by hand in the Supabase SQL editor |
| `scripts/load_historical_data.py` | One-off nflverse → Supabase loader, not part of the app |

Helper modules are imported by `app.py` and must not import `app.py` back
(circular import).

## Rules that matter

- **Real data only.** Never invent odds, lines, scores, ADP or trends. If real
  data is missing, skip it or show sample data clearly labelled as sample.
- Bets price against the de-vigged MACHINE Consensus line, not a single book.
- Odds API free tier is ~500 credits/month: keep the 3-hour cache
  (`ODDS_API_TTL_SECONDS`) and don't add fetches on every rerun.
- Guest data (`users_db.json`, `bets.db`) is wiped on every redeploy; anything
  meant to persist goes to Supabase.
- Brand: black / white / grey / red (`#e10600`). Theme lives in
  `.streamlit/config.toml`. For chart profit/loss use teal `#0d9488` vs red,
  not green vs red (colour-blind safety).
- Commit messages are one imperative sentence describing the user-visible
  change, e.g. "Add game and matchup betting trends to every game card".
