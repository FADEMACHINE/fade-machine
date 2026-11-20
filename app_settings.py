"""Master Settings: admin-controlled knobs for the MACHINE MODEL.

Stored as one row in the Supabase `app_settings` table (db/admin_settings.sql).
Anyone can read it, so the app and the daily GitHub job both follow the same
settings; only accounts in `admin_users` can change it (enforced by the
database, not just hidden in the UI).

apply() pushes the saved values onto the model modules at the start of each run.
Every pick records which settings version it was made under (rules_version).
"""
from datetime import datetime, timezone

import streamlit as st

import auth_store
import cbb_board
import cbb_value

DEFAULTS = {
    "model_paused": False,     # stop logging plays and locking the Top 3 (grading continues)
    "play_at": 4,              # checks needed for a PLAY
    "require_core": True,      # a PLAY must be in a price lane with model value
    "min_value_pts": 3.0,
    "fav_lane_lo": -300, "fav_lane_hi": -150,
    "dog_lane_lo": 150, "dog_lane_hi": 300,
    "rest_edge_days": 2,
    "ft_edge": 3.0, "ft_min_pct": 70.0,
    "reb_edge": 3.0, "to_edge": 2.0,
    "top3_lock_hour": 10,      # ET
    "top_n": 3,                # picks per day (the table allows up to 3)
    "lookahead_days": 1,       # admin lookahead
}


def _clean(raw):
    """Defaults overlaid with saved values of the right type; unknown keys dropped."""
    out = dict(DEFAULTS)
    for k, default in DEFAULTS.items():
        if k not in (raw or {}):
            continue
        v = raw[k]
        try:
            out[k] = (bool(v) if isinstance(default, bool) else
                      int(v) if isinstance(default, int) else float(v))
        except (TypeError, ValueError):
            pass
    return out


@st.cache_data(ttl=5 * 60, show_spinner=False)
def load():
    """(settings, updated_at or None). Falls back to defaults if the table
    isn't set up or Supabase is unreachable."""
    c = cbb_board._client()
    if c is None:
        return dict(DEFAULTS), None
    try:
        rows = c.table("app_settings").select("settings,updated_at").eq("id", "global") \
            .limit(1).execute().data or []
    except Exception:
        return dict(DEFAULTS), None
    if not rows:
        return dict(DEFAULTS), None
    return _clean(rows[0].get("settings")), rows[0].get("updated_at")


def apply(settings=None, updated_at=None):
    """Point the model modules at the saved settings for this run."""
    if settings is None:
        settings, updated_at = load()
    r = cbb_value.RULES
    r["play_at"] = settings["play_at"]
    r["min_value_pts"] = settings["min_value_pts"]
    r["fav_lane"] = (settings["fav_lane_lo"], settings["fav_lane_hi"])
    r["dog_lane"] = (settings["dog_lane_lo"], settings["dog_lane_hi"])
    r["rest_edge_days"] = settings["rest_edge_days"]
    r["ft_edge"] = settings["ft_edge"]
    r["ft_min_pct"] = settings["ft_min_pct"]
    r["reb_edge"] = settings["reb_edge"]
    r["to_edge"] = settings["to_edge"]
    cbb_value.REQUIRE_CORE = settings["require_core"]
    cbb_value.LOOKAHEAD_DAYS = settings["lookahead_days"]
    cbb_board.TOP3_LOCK_HOUR = settings["top3_lock_hour"]
    cbb_board.TOP_N = max(1, min(3, settings["top_n"]))
    cbb_board.PAUSED = settings["model_paused"]
    cbb_board.RULES_VERSION = "v1" if not updated_at else f"v1-{str(updated_at)[:16]}"
    return settings


def save(settings):
    """Write settings as the signed-in admin. Returns error text or None."""
    c, uid = auth_store.client(), auth_store.current_user_id()
    if c is None or not uid:
        return "Sign in first."
    try:
        c.table("app_settings").upsert({
            "id": "global", "settings": _clean(settings),
            "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": uid,
        }, on_conflict="id").execute()
    except Exception as e:
        msg = str(e)
        if "app_settings" in msg and ("does not exist" in msg or "schema cache" in msg):
            return "The settings table isn't set up yet. Run db/admin_settings.sql in Supabase."
        if "row-level security" in msg or "42501" in msg:
            return "Supabase refused the change: this account isn't in admin_users."
        return f"Couldn't save: {msg[:160]}"
    load.clear()
    return None


def _hour_label(h):
    return f"{(h - 1) % 12 + 1} {'AM' if h < 12 else 'PM'} ET"


def render_admin_settings():
    """The Master Settings panel. Only call it for admins."""
    settings, updated_at = load()
    st.caption("Master controls for the MACHINE MODEL. Changes apply to the app and the daily "
               "job within about 5 minutes. Picks already made keep the settings they were made "
               "under; new picks record the new settings version.")
    if updated_at:
        st.caption(f"Last changed {str(updated_at)[:16].replace('T', ' ')} UTC")

    with st.form("master_settings"):
        st.markdown("**Machine Model**")
        paused = st.toggle("Pause the Machine Model", value=settings["model_paused"],
                           help="Stops logging new plays and locking the Top 3. Grading of "
                                "existing picks keeps going.")

        st.markdown("**Checklist**")
        c = st.columns(2)
        play_at = c[0].slider("Checks needed to qualify", 3, 8, settings["play_at"])
        min_value = c[1].number_input("Minimum model value (pts)", 0.0, 20.0,
                                      float(settings["min_value_pts"]), step=0.5)
        require_core = st.checkbox("Require price lane + model value", value=settings["require_core"])
        c = st.columns(4)
        fav_lo = c[0].number_input("Fav lane from", -2000, -101, int(settings["fav_lane_lo"]), step=5)
        fav_hi = c[1].number_input("Fav lane to", -2000, -101, int(settings["fav_lane_hi"]), step=5)
        dog_lo = c[2].number_input("Dog lane from", 100, 2000, int(settings["dog_lane_lo"]), step=5)
        dog_hi = c[3].number_input("Dog lane to", 100, 2000, int(settings["dog_lane_hi"]), step=5)
        c = st.columns(5)
        rest = c[0].number_input("Rest edge (days)", 1, 7, int(settings["rest_edge_days"]))
        ft_edge = c[1].number_input("FT edge", 0.0, 20.0, float(settings["ft_edge"]), step=0.5)
        ft_min = c[2].number_input("Min FT %", 50.0, 90.0, float(settings["ft_min_pct"]), step=1.0)
        reb = c[3].number_input("Rebound edge", 0.0, 20.0, float(settings["reb_edge"]), step=0.5)
        to = c[4].number_input("Turnover edge", 0.0, 20.0, float(settings["to_edge"]), step=0.5)

        st.markdown("**MACHINE Top 3**")
        c = st.columns(2)
        lock = c[0].selectbox("Lock time", list(range(8, 17)),
                              index=list(range(8, 17)).index(settings["top3_lock_hour"])
                              if settings["top3_lock_hour"] in range(8, 17) else 2,
                              format_func=_hour_label)
        top_n = c[1].slider("Picks per day", 1, 3, settings["top_n"])

        st.markdown("**Admin lookahead**")
        look = st.slider("Days ahead to scope", 0, 3, settings["lookahead_days"])

        saved = st.form_submit_button("Save settings", type="primary")

    if saved:
        new = {"model_paused": paused, "play_at": play_at, "require_core": require_core,
               "min_value_pts": min_value, "fav_lane_lo": fav_lo, "fav_lane_hi": fav_hi,
               "dog_lane_lo": dog_lo, "dog_lane_hi": dog_hi, "rest_edge_days": rest,
               "ft_edge": ft_edge, "ft_min_pct": ft_min, "reb_edge": reb, "to_edge": to,
               "top3_lock_hour": lock, "top_n": top_n, "lookahead_days": look}
        if fav_lo > fav_hi or dog_lo > dog_hi:
            st.error("Each lane's 'from' must be the longer price: e.g. favourites -300 to -150, dogs +150 to +300.")
        else:
            err = save(new)
            st.error(err) if err else st.success("Saved. The model uses these settings from now on.")

    if st.button("Reset to defaults", key="master_reset"):
        err = save(dict(DEFAULTS))
        st.error(err) if err else st.success("Reset to the default settings.")
