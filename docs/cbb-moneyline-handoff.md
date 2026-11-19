# Handoff from claude.ai chat — CBB moneyline model (Nov 19, 2026)

Context for Claude Code: the owner analyzed a year of personal Juice Reel betting
history in a claude.ai chat and wants to build the resulting checklist into
FADE MACHINE as a feature that flags matching college basketball (CBB) bets.
Main already has College Hoops changes - build on those rather than duplicating.

## What the data showed (straight bets, Nov 2025 - Nov 2026)
- Edge is in MONEYLINES, not spreads. CBB moneylines +33% ROI (112 bets); CBB spreads -14% (379 bets).
- Best odds lanes: favorites -150 to -300 (+17% ROI, 104 bets) and dogs +150 to +300 (+45%, 37 bets - small sample).
- Weak: coin-flip range -101 to -149 (+4%). Long shots past +300 lost (0-5). Parlays lost all year.

## Checklist the feature should score (CBB)
1. Price lane - book moneyline in -150..-300 or +150..+300
2. Model value - model win% converted to fair odds vs. book implied % (e.g. 59.8% = -149 fair vs -115 book = ~6 pts value)
3. Roster continuity - returning minutes
4. Schedule/fatigue - back-to-backs, multi-day events, travel, time zones
5. Motivation - consolation games, letdown spots
6. Free throws - FT% and FT rate (FTA/FGA)
7. Rebounding - offensive reb rate vs opponent defensive reb rate
8. Guards/turnovers - TO rate, forced TO rate
9. Shooting profile - 3PT reliance vs interior scoring
10. Ratings lag - before mid-December, ratings still lean on preseason priors
Flag only (not scored): neutral site, or "neutral" venue near one campus.
Rule: play when 4-5+ checks agree; otherwise pass.

## Data sources discussed
- Bart Torvik (https://barttorvik.com/) - free efficiency + four-factor stats. Start here.
- The Odds API - already used by this app (ODDS_API_KEY); has NCAAB moneylines.
- CollegeBasketballData.com - free API key, historical games/box scores.
- sportsdataverse (Python) - ESPN schedules/play-by-play.
- KenPom - paid, no API, scraping breaks ToS. Don't build on it.

## Suggested first version
A "CBB Value" view: pull today's NCAAB moneylines, join Torvik team stats,
compute implied vs. fair probability, score the checklist, and list games
that pass. Keep it read-only analytics like the rest of the app.
