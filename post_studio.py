"""Post Studio: turn the day's picks into ready-to-post X drafts and a pick card.

Private owner tool, opened with ?studio=1 and unlocked with POST_STUDIO_PASSCODE
from st.secrets. Flow: paste picks -> each pick is matched to a game on the live
odds board (real MACHINE Consensus line + real historical matchup trends) ->
drafts are written -> edit -> download the image or post straight to X.

Real data only: drafts may quote the owner's own picks and notes, the live
consensus line and computed trends. Nothing else. Claude drafting (optional,
ANTHROPIC_API_KEY) is told the same and given only those facts.
"""
import hmac
import io
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

import matchup_trends as mtr
import x_poster
from bet_slips import fmt_odds

ET = ZoneInfo("America/New_York")
BRAND_RED = "#e10600"
CLAUDE_MODEL = "claude-opus-5-5"


# ---- Access ----------------------------------------------------------------
def _secret(name):
    try:
        return st.secrets.get(name)
    except Exception:
        return None


def _unlocked():
    passcode = _secret("POST_STUDIO_PASSCODE")
    if not passcode:
        st.info("Post Studio is locked. Add `POST_STUDIO_PASSCODE` to `st.secrets` to use it.")
        return False
    if st.session_state.get("studio_ok"):
        return True
    entered = st.text_input("Studio passcode", type="password", key="studio_pass")
    if entered:
        if hmac.compare_digest(entered, str(passcode)):
            st.session_state["studio_ok"] = True
            st.rerun()
        st.error("Wrong passcode.")
    return False


# ---- Facts (real data only) ------------------------------------------------
def _nickname(team):
    return team.split()[-1].lower() if team else ""


def match_game(pick_line, games):
    """First game whose full team name or nickname appears in the pick line."""
    text = pick_line.lower()
    words = set(text.replace("/", " ").replace(",", " ").split())
    for g in games or []:
        for team in (g["away"], g["home"]):
            if team.lower() in text or _nickname(team) in words:
                return g, team
    return None, None


def _rec_str(r):
    body = f"{r['w']}-{r['l']}" + (f"-{r['p']}" if r["p"] else "")
    return body


def _trend_facts(game, team):
    """A few computed, non-thin trend lines for the picked side's game."""
    try:
        df = mtr.games_frame()
        t = mtr.matchup_trends(df, game["away"], game["home"], mtr.team_name_map())
    except Exception:
        t = None
    if not t:
        return []
    side = "away" if team == game["away"] else "home"
    venue = "on the road" if side == "away" else "at home"
    facts = []
    s = t[side]
    if not s["form"]["thin"]:
        facts.append(f"{team} are {_rec_str(s['form'])} ATS in their last {s['form']['n']} games")
    if not s["venue"]["thin"]:
        facts.append(f"{team} are {_rec_str(s['venue'])} ATS {venue} in their last {s['venue']['n']}")
    h = t["h2h"]
    if h["meetings"] and not h["ats"]["thin"]:
        facts.append(
            f"{game['away']} are {_rec_str(h['ats'])} ATS vs {game['home']} in the last {h['meetings']} meetings"
        )
    if h["avg_total"] is not None and h["meetings"] >= mtr.MIN_SAMPLE:
        facts.append(f"Last {h['meetings']} meetings averaged {h['avg_total']} total points")
    return facts


def _line_facts(game):
    c = game.get("consensus") or {}
    out = []
    if "spreads" in c:
        sp = c["spreads"]
        out.append(f"MACHINE Consensus spread: {game['away']} {sp['away_point']:+g} / "
                   f"{game['home']} {sp['home_point']:+g}")
    if "totals" in c:
        out.append(f"MACHINE Consensus total: {c['totals']['point']:g}")
    if "h2h" in c:
        out.append(f"MACHINE Consensus moneyline: {game['away']} {fmt_odds(c['h2h']['away'])} / "
                   f"{game['home']} {fmt_odds(c['h2h']['home'])}")
    return out


def build_pick_facts(pick_lines, games, with_trends):
    picks = []
    for line in pick_lines:
        game, team = match_game(line, games)
        entry = {"pick": line, "game": None, "kickoff": None, "lines": [], "trends": []}
        if game:
            entry["game"] = f"{game['away']} @ {game['home']}"
            try:
                ko = datetime.fromisoformat(game["commence_time"].replace("Z", "+00:00")).astimezone(ET)
                entry["kickoff"] = ko.strftime("%a %-I:%M %p ET")
            except Exception:
                pass
            entry["lines"] = _line_facts(game)
            if with_trends:
                entry["trends"] = _trend_facts(game, team)
        picks.append(entry)
    return picks


# ---- Drafts ----------------------------------------------------------------
def template_drafts(picks, notes, cta):
    """Deterministic drafts built only from the picks and computed facts."""
    day = datetime.now(ET).strftime("%A")
    lines = [p["pick"] for p in picks]
    numbered = "\n".join(f"✅ {l}" for l in lines)
    drafts = []

    drafts.append({
        "label": "Card drop",
        "text": f"🎯 FADE MACHINE {day} card\n\n{numbered}\n\n{cta}".strip(),
    })

    top = picks[0]
    hook = top["trends"][0] if top["trends"] else (notes.split("\n")[0] if notes else "")
    body = f"🔴 Best bet: {top['pick']}"
    if hook:
        body += f"\n\n{hook}."
    body += "\n\nTail or fade? 👇"
    drafts.append({"label": "Best bet + reply bait", "text": body})

    if len(picks) > 1:
        drafts.append({
            "label": "Short + question",
            "text": f"{len(picks)} plays on the {day} card. Which one are you riding?\n\n{numbered}",
        })
    return drafts


SYSTEM_PROMPT = """You write X (Twitter) posts for FADE MACHINE (@Fade_Machine), an NFL betting \
analytics brand. The goal is follower growth and engagement ahead of the FADE MACHINE app launch.

Hard rules:
- Use ONLY the facts provided: the owner's picks, the owner's notes, the consensus lines and the \
computed trends. Never invent records, stats, injuries, lines, odds, results or a track record.
- Keep every pick exactly as the owner wrote it (team, number, price, units).
- Every post must fit in 280 characters, counting emojis and line breaks.
- No guarantees ("lock", "can't lose", "free money") and no claims about the owner's past results.

What tends to drive engagement on betting X:
- A strong first line (the hook) that makes people stop scrolling.
- Short lines and white space; 1-3 emojis max; at most one or two relevant hashtags.
- A reason to reply: a question, "tail or fade?", a poll-style prompt.
- One concrete, real data point beats several vague ones.
- Occasionally a soft nod to the app if a call to action is supplied."""


def claude_drafts(picks, notes, cta, n=4):
    """Returns (drafts, error). Needs ANTHROPIC_API_KEY in st.secrets."""
    key = _secret("ANTHROPIC_API_KEY")
    if not key:
        return None, "missing_key"
    try:
        import anthropic
    except ImportError:
        return None, "The `anthropic` package is not installed."

    facts = {"date": datetime.now(ET).strftime("%A %B %-d"), "picks": picks,
             "owner_notes": notes or None, "call_to_action": cta or None}
    schema = {
        "type": "object",
        "properties": {
            "drafts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string", "description": "2-4 word name for the angle"},
                        "text": {"type": "string"},
                        "why": {"type": "string", "description": "One sentence on why it should engage"},
                    },
                    "required": ["label", "text", "why"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["drafts"],
        "additionalProperties": False,
    }
    client = anthropic.Anthropic(api_key=key)
    try:
        resp = client.beta.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM_PROMPT,
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
            messages=[{
                "role": "user",
                "content": f"Write {n} different post drafts for today's picks, each a different "
                           f"angle (e.g. card drop, best-bet spotlight, data hook, question).\n\n"
                           f"Facts (JSON):\n{json.dumps(facts, indent=2)}",
            }],
        )
    except anthropic.AuthenticationError:
        return None, "ANTHROPIC_API_KEY was rejected."
    except anthropic.RateLimitError:
        return None, "Claude is rate limited right now. Try again in a minute."
    except anthropic.APIStatusError as e:
        return None, f"Claude API error {e.status_code}: {e.message}"
    except anthropic.APIConnectionError:
        return None, "Couldn't reach the Claude API."
    if resp.stop_reason == "refusal":
        return None, "Claude declined to draft this one."
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        drafts = json.loads(text)["drafts"]
    except (ValueError, KeyError):
        return None, "Claude returned something unreadable. Try again."
    return drafts, None


# ---- Pick card image -------------------------------------------------------
def _font(size, bold=False):
    from PIL import ImageFont
    names = (["DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf"] if bold
             else ["DejaVuSans.ttf", "Arial.ttf", "arial.ttf"])
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _wrap(draw, text, font, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def pick_card_png(picks, title):
    """1200x1200 black/white/red card listing the picks (X shows 1:1 well)."""
    from PIL import Image, ImageDraw
    W = H = 1200
    pad = 80
    img = Image.new("RGB", (W, H), "#0a0a0a")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 18], fill=BRAND_RED)
    d.text((pad, 70), "FADE MACHINE", font=_font(84, True), fill="#ffffff")
    d.text((pad, 175), title.upper(), font=_font(38, True), fill=BRAND_RED)
    d.line([pad, 245, W - pad, 245], fill="#3a3a3a", width=3)

    y = 285
    pick_font, sub_font = _font(46, True), _font(28)
    for p in picks:
        if y > H - 220:
            d.text((pad, y), "+ more on the timeline", font=sub_font, fill="#9a9a9a")
            break
        d.rectangle([pad, y + 8, pad + 10, y + 52], fill=BRAND_RED)
        for i, line in enumerate(_wrap(d, p["pick"], pick_font, W - 2 * pad - 40)[:2]):
            d.text((pad + 34, y), line, font=pick_font, fill="#ffffff")
            y += 58
        sub = " · ".join(x for x in (p.get("game"), p.get("kickoff")) if x)
        if sub:
            d.text((pad + 34, y), sub, font=sub_font, fill="#9a9a9a")
            y += 40
        y += 34

    d.line([pad, H - 140, W - pad, H - 140], fill="#3a3a3a", width=3)
    d.text((pad, H - 110), "@Fade_Machine", font=_font(40, True), fill="#ffffff")
    d.text((W - pad - 520, H - 102), "Play responsibly. 21+.", font=_font(30), fill="#9a9a9a")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---- Page ------------------------------------------------------------------
def render_post_studio(games, odds_err=None):
    st.markdown("## ✍️ Post Studio")
    st.caption("Paste today's picks → get X drafts and a pick card → edit → post. Private owner tool.")
    if not _unlocked():
        return

    if odds_err:
        st.info("Live odds aren't available, so picks won't be matched to consensus lines or trends.")

    picks_text = st.text_area(
        "Today's picks (one per line, as you'd post them)",
        key="studio_picks", height=140,
        placeholder="Bills -3 (-110) 2u\nChiefs/Raiders Over 44.5 1u",
    )
    notes = st.text_area("Your angle / notes (optional, used as-is)", key="studio_notes", height=80)
    c1, c2 = st.columns(2)
    cta = c1.text_input("Call to action (optional)", key="studio_cta",
                        placeholder="FADE MACHINE app coming soon 👀")
    with_trends = c2.checkbox("Add real matchup trends", value=True, key="studio_trends")

    pick_lines = [l.strip() for l in (picks_text or "").splitlines() if l.strip()]
    if not pick_lines:
        return

    picks = build_pick_facts(pick_lines, games or [], with_trends)
    with st.expander("Facts the drafts can use", expanded=False):
        for p in picks:
            st.markdown(f"**{p['pick']}**" + (f" — {p['game']} ({p['kickoff']})" if p["game"] else " — no game match"))
            for f in p["lines"] + p["trends"]:
                st.markdown(f"- {f}")

    b1, b2 = st.columns(2)
    if b1.button("Write drafts", type="primary", width="stretch", key="studio_tmpl"):
        st.session_state["studio_drafts"] = template_drafts(picks, notes, cta)
    if b2.button("Write drafts with Claude", width="stretch", key="studio_ai"):
        with st.spinner("Claude is drafting…"):
            drafts, err = claude_drafts(picks, notes, cta)
        if err == "missing_key":
            st.info("Add `ANTHROPIC_API_KEY` to `st.secrets` to draft with Claude. Template drafts work without it.")
        elif err:
            st.error(err)
        else:
            st.session_state["studio_drafts"] = drafts

    drafts = st.session_state.get("studio_drafts")
    if not drafts:
        return

    labels = [f"{i + 1}. {d['label']}" for i, d in enumerate(drafts)]
    choice = st.radio("Pick a draft", labels, key="studio_choice", horizontal=True)
    draft = drafts[labels.index(choice)]
    if draft.get("why"):
        st.caption(draft["why"])
    # Keyed per draft so switching drafts loads that draft's text, while edits stick.
    text = st.text_area("Edit", value=draft["text"], height=200, key=f"studio_edit_{choice}")
    n = x_poster.tweet_length(text)
    (st.caption if n <= x_poster.MAX_CHARS else st.error)(f"{n}/{x_poster.MAX_CHARS} characters")
    st.code(text, language=None)  # tap the copy icon to paste into X yourself

    title = st.text_input("Card title", value=f"{datetime.now(ET).strftime('%A')} card", key="studio_card_title")
    png = pick_card_png(picks, title)
    st.image(png, caption="Pick card", width=420)
    st.download_button("Download image", png, file_name="fade_machine_card.png",
                       mime="image/png", key="studio_dl")

    st.divider()
    if not x_poster.is_configured():
        st.info("To post from here, add `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN` and "
                "`X_ACCESS_SECRET` to `st.secrets`. Until then, copy the text and download the image.")
        return
    attach = st.checkbox("Attach pick card", value=True, key="studio_attach")
    confirm = st.checkbox("I've checked it — post to @Fade_Machine", key="studio_confirm")
    if st.button("Post to X", type="primary", disabled=not confirm or n > x_poster.MAX_CHARS, key="studio_post"):
        with st.spinner("Posting…"):
            url, err = x_poster.post_tweet(text, png if attach else None)
        if err:
            st.error(err)
        else:
            st.success(f"Posted: {url}")
