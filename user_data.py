"""Routes bet reads and writes to the right backend.

Signed in  -> Supabase (durable; survives redeploys)
Guest      -> local SQLite ledger (scratch; wiped whenever the host resets)

Every caller in app.py goes through here so the branch lives in one place
rather than being repeated at each call site.
"""
import auth_store
import bet_store


def is_durable():
    """True when the current user's data is being stored durably."""
    return auth_store.signed_in()


def backend_label():
    return "Supabase" if is_durable() else "local (this session only)"


def record_bet(username, bet):
    if is_durable():
        return auth_store.record_bet(bet)
    return bet_store.record_bet(username, bet)


def bets_for(username, status=None):
    if is_durable():
        return auth_store.bets_for(status)
    return bet_store.bets_for(username, status)


def open_bets_with_games(username):
    if is_durable():
        return auth_store.open_bets_with_games()
    return bet_store.open_bets_with_games(username)


def mark_settled(bet_id, status, steel_result, settled_at,
                 away_score=None, home_score=None, note=None):
    if is_durable():
        return auth_store.mark_settled(
            bet_id, status, steel_result, settled_at,
            away_score, home_score, note,
        )
    return bet_store.mark_settled(
        bet_id, status, steel_result, settled_at,
        away_score, home_score, note,
    )


def history_rows(username):
    return bets_for(username)
