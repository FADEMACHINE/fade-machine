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
- `CBBD_API_KEY` — CollegeBasketballData.com (CBB team stats for the checklist). Free key = 1,000 calls/month: keep the 12-hour cache and the job's two scoring runs a day

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
| `auth_store.py`, `auth_ui.py` | Optional Supabase sign-in, cookie-backed sessions. One Supabase client per browser session (never shared); refresh tokens rotate, so every refresh writes the new one back to the cookie. `is_admin()` = row in `admin_users` |
| `app_settings.py` | Admin Master Settings (Profile → ⚙️ Master Settings): checklist thresholds, Top 3 lock time/size, lookahead, pause. Stored in Supabase `app_settings` (db/admin_settings.sql); `apply()` pushes them onto the model for the app and the daily job |
| `bet_settlement.py` | Settles open bets from The Odds API `/scores` |
| `bet_slips.py` | Groups repeat bets into slips; the My Bets tab |
| `bet_analytics.py` | Bet history and trend charts on the Profile tab |
| `content_engine.py` | Headlines, leaderboards and movers derived from the data |
| `cbb_data.py` | College basketball: ESPN scoreboard fetch (no key, no Odds API credits) and the MACHINE ratings model (normal equations summed directly, cached 30 min; never build the full design matrix) |
| `cbb_edges.py` | Editable list of CBB edges flagged on the ratings and March Madness cheat sheet |
| `cbb_value.py` | CBB Value: scores the owner's moneyline checklist (docs/cbb-moneyline-handoff.md) with CollegeBasketballData.com stats (Torvik as backup; Torvik blocks GitHub's servers) + ESPN lines; thresholds in `RULES` |
| `cbb_board.py` | Machine Model page: logs every CBB Value PLAY (`model_plays`) and the daily MACHINE Top 3 (`machine_top3`), both locked at the price found and graded from ESPN finals |
| `cbb_tab.py` | College Hoops tab: board, power ratings, team lookup, March Madness. Sections are lazy (`st.tabs(..., on_change="rerun")` + `.open`): only the open one is built |
| `real_bets.py` | Profile → Real Bets: Juice Reel CSV import (no API exists) and real-money ROI analysis; Supabase table in `db/real_bets.sql` |
| `post_studio.py` | Private `?studio=1` page: picks → X drafts, pick-card image, post |
| `x_poster.py` | X API v2 posting (OAuth 1.0a) and image upload |
| `fantasy_models.py`, `mock_draft.py` | Fantasy rankings and the mock-draft hub |
| `db/*.sql` | Supabase schema — run by hand in the Supabase SQL editor |
| `scripts/daily_model_check.py` | Run by `.github/workflows/daily-model-check.yml` several times a day: logs plays, locks the Top 3, grades results. Needs `SUPABASE_URL`, `SUPABASE_ANON_KEY` and `CBBD_API_KEY` as GitHub repo secrets |
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
