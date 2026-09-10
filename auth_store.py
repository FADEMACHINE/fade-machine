"""Supabase-backed accounts and durable bet storage for FADE MACHINE.

Signing in is optional: the app still opens into the local guest profile, and
only a signed-in account gets durable storage. That split is deliberate —
users_db.json and bets.db live on the app's filesystem, which Streamlit
Community Cloud wipes on redeploy, so guest data is scratch by nature and
anything meant to survive has to go to Supabase.

Passwords never pass through this module's storage. Supabase Auth owns them in
auth.users, hashed server-side; we hold an access token for the session and a
refresh token in a cookie. Every table is behind row level security keyed to
auth.uid() (db/auth_schema.sql), so the public anon key can only ever reach the
signed-in account's own rows.

Requires db/auth_schema.sql to have been run. Until it is, sign-in still works
but profile/bet reads fail — `tables_ready()` reports that, and callers show a
setup message rather than crashing.
"""
import streamlit as st

SESSION_KEY = "sb_session"
COOKIE_NAME = "fm_refresh"
COOKIE_DAYS = 30


class AuthError(Exception):
    """Sign-in / sign-up failure with a message safe to show a user."""


def _secrets():
    try:
        return st.secrets.get("SUPABASE_URL"), st.secrets.get("SUPABASE_ANON_KEY")
    except Exception:
        return None, None


def configured():
    url, key = _secrets()
    return bool(url and key)


@st.cache_resource(show_spinner=False)
def _client_for(url, key):
    from supabase import create_client
    return create_client(url, key)


def client():
    """A Supabase client carrying the current session's access token, if any.

    The token has to be re-applied per rerun: the client object is cached
    across reruns, but session state is what actually tracks who is signed in.
    """
    url, key = _secrets()
    if not (url and key):
        return None
    c = _client_for(url, key)
    sess = st.session_state.get(SESSION_KEY)
    if sess and sess.get("access_token"):
        try:
            c.postgrest.auth(sess["access_token"])
        except Exception:
            pass
    return c


def _store_session(session):
    """Keep only what's needed; never persist the password itself."""
    if not session:
        return None
    st.session_state[SESSION_KEY] = {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "user_id": session.user.id if session.user else None,
        "email": session.user.email if session.user else None,
    }
    return st.session_state[SESSION_KEY]


def current_session():
    return st.session_state.get(SESSION_KEY)


def current_user_id():
    s = current_session()
    return s.get("user_id") if s else None


def signed_in():
    return bool(current_user_id())


def _friendly(exc):
    msg = str(getattr(exc, "message", None) or exc)
    low = msg.lower()
    if "invalid login" in low or "invalid credentials" in low:
        return "Email or password is incorrect."
    if "already registered" in low or "already been registered" in low:
        return "That email already has an account — sign in instead."
    if "password" in low and ("least" in low or "short" in low):
        return "Password must be at least 6 characters."
    if "email" in low and "invalid" in low:
        return "That email address doesn't look valid."
    return msg[:200]


def sign_up(email, password, display_name=""):
    c = client()
    if c is None:
        raise AuthError("Supabase isn't configured — add SUPABASE_URL and SUPABASE_ANON_KEY.")
    try:
        res = c.auth.sign_up({
            "email": email,
            "password": password,
            "options": {"data": {"display_name": display_name or email.split("@")[0]}},
        })
    except Exception as e:
        raise AuthError(_friendly(e))
    if res.session:
        return _store_session(res.session)
    # Project has email confirmation switched on — no session until confirmed.
    return None


def sign_in(email, password):
    c = client()
    if c is None:
        raise AuthError("Supabase isn't configured — add SUPABASE_URL and SUPABASE_ANON_KEY.")
    try:
        res = c.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as e:
        raise AuthError(_friendly(e))
    if not res.session:
        raise AuthError("Sign-in failed — no session returned.")
    return _store_session(res.session)


def restore_from_refresh_token(token):
    """Re-establish a session from a stored refresh token (the cookie path)."""
    if not token:
        return None
    c = client()
    if c is None:
        return None
    try:
        res = c.auth.refresh_session(token)
    except Exception:
        return None
    return _store_session(res.session) if res and res.session else None


def sign_out():
    c = client()
    try:
        if c is not None:
            c.auth.sign_out()
    except Exception:
        pass
    st.session_state.pop(SESSION_KEY, None)


# ---- Durable data -----------------------------------------------------------
def tables_ready():
    """True once db/auth_schema.sql has been run against the project."""
    c = client()
    if c is None:
        return False
    try:
        c.table("profiles").select("id").limit(1).execute()
        return True
    except Exception:
        return False


def get_profile():
    uid = current_user_id()
    c = client()
    if not uid or c is None:
        return None
    try:
        res = c.table("profiles").select("*").eq("id", uid).limit(1).execute()
    except Exception:
        return None
    rows = res.data or []
    if rows:
        return rows[0]
    # The signup trigger normally creates this; insert as a fallback so a
    # project missing the trigger still works.
    try:
        sess = current_session() or {}
        name = (sess.get("email") or "player").split("@")[0]
        c.table("profiles").insert(
            {"id": uid, "display_name": name, "steel_balance": 0}
        ).execute()
        return {"id": uid, "display_name": name, "steel_balance": 0}
    except Exception:
        return None


def set_steel_balance(balance):
    uid = current_user_id()
    c = client()
    if not uid or c is None:
        return False
    try:
        c.table("profiles").update({"steel_balance": balance}).eq("id", uid).execute()
        return True
    except Exception:
        return False


def add_transaction(tx_type, amount, note=""):
    uid = current_user_id()
    c = client()
    if not uid or c is None:
        return False
    try:
        c.table("steel_transactions").insert({
            "user_id": uid, "type": tx_type,
            "steel_amount": amount, "note": note[:400],
        }).execute()
        return True
    except Exception:
        return False


def transactions(limit=200):
    uid = current_user_id()
    c = client()
    if not uid or c is None:
        return []
    try:
        res = (c.table("steel_transactions").select("*")
               .eq("user_id", uid).order("created_at", desc=True)
               .limit(limit).execute())
        return res.data or []
    except Exception:
        return []


BET_FIELDS = [
    "id", "game_id", "away", "home", "market", "market_type", "selection",
    "line", "odds", "stake", "player", "label", "placed_at", "commence_time",
    "status", "steel_result", "settled_at", "away_score", "home_score",
    "settle_note",
]


def record_bet(bet):
    uid = current_user_id()
    c = client()
    if not uid or c is None:
        return False
    row = {k: bet.get(k) for k in BET_FIELDS}
    row["user_id"] = uid
    row["status"] = bet.get("status") or "open"
    row["steel_result"] = bet.get("steel_result") or 0
    try:
        c.table("bets").upsert(row, on_conflict="id").execute()
        return True
    except Exception:
        return False


def bets_for(status=None):
    uid = current_user_id()
    c = client()
    if not uid or c is None:
        return []
    try:
        q = c.table("bets").select("*").eq("user_id", uid)
        if status == "open":
            q = q.eq("status", "open")
        elif status == "settled":
            q = q.neq("status", "open")
        return (q.order("placed_at", desc=True).execute().data) or []
    except Exception:
        return []


def open_bets_with_games():
    return [b for b in bets_for("open") if b.get("game_id")]


def mark_settled(bet_id, status, steel_result, settled_at,
                 away_score=None, home_score=None, note=None):
    uid = current_user_id()
    c = client()
    if not uid or c is None:
        return False
    try:
        (c.table("bets").update({
            "status": status, "steel_result": steel_result,
            "settled_at": settled_at, "away_score": away_score,
            "home_score": home_score, "settle_note": note,
        }).eq("id", bet_id).eq("user_id", uid).execute())
        return True
    except Exception:
        return False


def import_local_bets(rows):
    """Move guest bets into the signed-in account (upsert, so it's safe to
    re-run). Returns how many were sent."""
    uid = current_user_id()
    c = client()
    if not uid or c is None or not rows:
        return 0
    payload = []
    for b in rows:
        row = {k: b.get(k) for k in BET_FIELDS}
        row["user_id"] = uid
        row["status"] = b.get("status") or "open"
        row["steel_result"] = b.get("steel_result") or 0
        payload.append(row)
    try:
        c.table("bets").upsert(payload, on_conflict="id").execute()
        return len(payload)
    except Exception:
        return 0
