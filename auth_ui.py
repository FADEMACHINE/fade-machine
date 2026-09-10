"""Sign-in / create-account UI and cookie-backed session restore.

Sign-in is optional — the app opens into the guest profile and this only ever
appears on the Profile tab. What signing in buys you is durability: a guest's
bets and balance live on the app's filesystem and vanish when the host resets,
while a signed-in account's live in Supabase.

The cookie holds only Supabase's refresh token, never a password. Streamlit can
read cookies (st.context.cookies) but not write them, hence the component.
"""
import streamlit as st

import auth_store

_COOKIE_KEY = "fm_cookie_mgr"


def _cookie_manager():
    """CookieManager, or None if the component isn't installed.

    Kept optional on purpose: without it everything still works, you just get
    signed out on a full browser refresh instead of being remembered.
    """
    try:
        import extra_streamlit_components as stx
    except Exception:
        return None
    if _COOKIE_KEY not in st.session_state:
        st.session_state[_COOKIE_KEY] = stx.CookieManager(key="fm_cookies")
    return st.session_state[_COOKIE_KEY]


def _read_refresh_token():
    """Prefer the component's view; fall back to Streamlit's read-only cookies."""
    mgr = _cookie_manager()
    if mgr is not None:
        try:
            val = mgr.get(auth_store.COOKIE_NAME)
            if val:
                return val
        except Exception:
            pass
    try:
        return st.context.cookies.get(auth_store.COOKIE_NAME)
    except Exception:
        return None


def _write_refresh_token(token):
    from datetime import datetime, timedelta, timezone
    mgr = _cookie_manager()
    if mgr is None or not token:
        return
    try:
        mgr.set(
            auth_store.COOKIE_NAME, token,
            expires_at=datetime.now(timezone.utc) + timedelta(days=auth_store.COOKIE_DAYS),
            key="fm_cookie_set",
        )
    except Exception:
        pass


def _clear_refresh_token():
    mgr = _cookie_manager()
    if mgr is None:
        return
    try:
        mgr.delete(auth_store.COOKIE_NAME, key="fm_cookie_del")
    except Exception:
        pass


def restore_session():
    """Re-sign-in from the stored refresh token. Runs once per session."""
    if auth_store.signed_in() or st.session_state.get("_auth_restore_tried"):
        return
    st.session_state["_auth_restore_tried"] = True
    if not auth_store.configured():
        return
    token = _read_refresh_token()
    if token:
        auth_store.restore_from_refresh_token(token)


def render_account_panel(local_bets_getter=None):
    """The Account panel: sign in / create account, or the signed-in summary."""
    if not auth_store.configured():
        st.info(
            "Accounts are offline: no `SUPABASE_URL` / `SUPABASE_ANON_KEY` in "
            "`st.secrets`. You're on the local guest profile — bets are kept "
            "on this machine only."
        )
        return

    if auth_store.signed_in():
        _render_signed_in(local_bets_getter)
        return

    st.markdown(
        "<div style='font-size:0.7rem;color:var(--muted,#a6a8ad);font-weight:600;"
        "letter-spacing:0.8px;margin-bottom:2px'>GUEST MODE</div>"
        "<div style='color:var(--muted,#a6a8ad);font-size:0.9rem;margin-bottom:10px'>"
        "You're browsing as a guest. Bets and Steel are stored on this machine "
        "and are wiped whenever the app redeploys. Sign in to keep your balance, "
        "bets and history permanently.</div>",
        unsafe_allow_html=True,
    )

    tab_in, tab_up = st.tabs(["Sign in", "Create account"])
    with tab_in:
        with st.form("fm_signin", clear_on_submit=False):
            email = st.text_input("Email", key="fm_in_email")
            pw = st.text_input("Password", type="password", key="fm_in_pw")
            remember = st.checkbox(
                "Keep me signed in", value=True, key="fm_in_remember",
                help="Stores a refresh token in a cookie on this browser.",
            )
            if st.form_submit_button("Sign in", type="primary"):
                try:
                    sess = auth_store.sign_in(email.strip(), pw)
                except auth_store.AuthError as e:
                    st.error(str(e))
                else:
                    if remember and sess:
                        _write_refresh_token(sess.get("refresh_token"))
                    st.success("Signed in.")
                    st.rerun()

    with tab_up:
        with st.form("fm_signup", clear_on_submit=False):
            email2 = st.text_input("Email", key="fm_up_email")
            name2 = st.text_input("Display name (optional)", key="fm_up_name")
            pw2 = st.text_input("Password", type="password", key="fm_up_pw",
                                help="At least 6 characters.")
            if st.form_submit_button("Create account", type="primary"):
                if len(pw2) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    try:
                        sess = auth_store.sign_up(email2.strip(), pw2, name2.strip())
                    except auth_store.AuthError as e:
                        st.error(str(e))
                    else:
                        if sess:
                            _write_refresh_token(sess.get("refresh_token"))
                            st.success("Account created — you're signed in.")
                            st.rerun()
                        else:
                            st.info(
                                "Account created. Check your email to confirm it, "
                                "then sign in."
                            )


def _render_signed_in(local_bets_getter):
    sess = auth_store.current_session() or {}
    profile = auth_store.get_profile()

    if profile is None:
        st.error(
            "Signed in, but the account tables aren't there yet. Run "
            "`db/auth_schema.sql` in your Supabase SQL editor, then reload."
        )
    else:
        st.success(f"Signed in as **{profile.get('display_name') or sess.get('email')}**")
        c1, c2 = st.columns(2)
        c1.metric("Steel balance", f"{profile.get('steel_balance', 0):.0f}")
        c2.metric("Storage", "Supabase", "Durable — survives redeploys",
                  delta_color="off")

    # Offer to carry guest bets over, once, if there are any.
    if local_bets_getter and profile is not None:
        local_rows = local_bets_getter() or []
        if local_rows:
            st.markdown("---")
            st.caption(
                f"{len(local_rows)} bet(s) are sitting in this machine's guest "
                f"ledger. Import them into your account so they're kept for good?"
            )
            if st.button("⬆ Import guest bets", key="fm_import_guest"):
                n = auth_store.import_local_bets(local_rows)
                st.success(f"Imported {n} bet(s).") if n else st.error("Import failed.")
                st.rerun()

    st.markdown("---")
    if st.button("Sign out", key="fm_signout"):
        auth_store.sign_out()
        _clear_refresh_token()
        st.rerun()
