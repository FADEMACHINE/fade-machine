"""SQLite ledger for every Steel bet placed in FADE MACHINE.

Bets used to live inside users_db.json as two nested lists per account, which
made them impossible to query — settlement, history and any trend analysis all
had to load and rewrite the whole blob. They now live in a real table with
indexes, so the analytics views are plain SQL.

Why SQLite and not Supabase: the live app only carries the anon key and is
read-only against Supabase by design (see db/schema.sql — the service_role key
is reserved for the offline ingestion script). Writing bets there would mean
shipping a write-capable key with the app. SQLite keeps that posture and is
still a large step up from a JSON blob. The trade-off is that the file is
local, so on an ephemeral host (Streamlit Community Cloud) it resets on
redeploy — exactly as users_db.json already does, so nothing regresses.

Accounts and Steel balances stay in users_db.json; this module owns the bet
ledger only. Settlement writes the P/L here and credits the balance there.
"""
import json
import os
import sqlite3
import threading

import pandas as pd
import streamlit as st

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bets.db")

# sqlite3 connections aren't safe to share across threads without care, and
# Streamlit serves reruns from a pool. One connection guarded by a lock is
# plenty for this workload and avoids a connection per rerun.
_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS bets (
    id            TEXT PRIMARY KEY,
    username      TEXT NOT NULL,
    game_id       TEXT,
    away          TEXT,
    home          TEXT,
    market        TEXT,
    market_type   TEXT,
    selection     TEXT,
    line          REAL,
    odds          INTEGER,
    stake         REAL NOT NULL DEFAULT 0,
    player        TEXT,
    label         TEXT,
    placed_at     TEXT,
    commence_time TEXT,
    status        TEXT NOT NULL DEFAULT 'open',
    steel_result  REAL NOT NULL DEFAULT 0,
    settled_at    TEXT,
    away_score    INTEGER,
    home_score    INTEGER,
    settle_note   TEXT
);
CREATE INDEX IF NOT EXISTS idx_bets_user        ON bets(username);
CREATE INDEX IF NOT EXISTS idx_bets_user_status ON bets(username, status);
CREATE INDEX IF NOT EXISTS idx_bets_game        ON bets(game_id);
CREATE INDEX IF NOT EXISTS idx_bets_placed      ON bets(username, placed_at);
"""

COLUMNS = [
    "id", "username", "game_id", "away", "home", "market", "market_type",
    "selection", "line", "odds", "stake", "player", "label", "placed_at",
    "commence_time", "status", "steel_result", "settled_at", "away_score",
    "home_score", "settle_note",
]


@st.cache_resource(show_spinner=False)
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    with _LOCK:
        conn.executescript(SCHEMA)
        conn.commit()
    return conn


def _rows_to_dicts(rows):
    return [dict(r) for r in rows]


def record_bet(username, bet):
    """Insert a newly placed bet. Idempotent on the bet's own id."""
    row = {c: bet.get(c) for c in COLUMNS}
    row["username"] = username
    row["status"] = bet.get("status") or "open"
    row["steel_result"] = bet.get("steel_result") or 0
    conn = get_conn()
    with _LOCK:
        conn.execute(
            f"INSERT OR IGNORE INTO bets ({','.join(COLUMNS)}) "
            f"VALUES ({','.join(':' + c for c in COLUMNS)})",
            row,
        )
        conn.commit()
    return row


def mark_settled(bet_id, status, steel_result, settled_at,
                 away_score=None, home_score=None, note=None):
    conn = get_conn()
    with _LOCK:
        conn.execute(
            "UPDATE bets SET status=?, steel_result=?, settled_at=?, "
            "away_score=?, home_score=?, settle_note=? WHERE id=?",
            (status, steel_result, settled_at, away_score, home_score, note, bet_id),
        )
        conn.commit()


def bets_for(username, status=None):
    conn = get_conn()
    sql = "SELECT * FROM bets WHERE username=?"
    args = [username]
    if status == "open":
        sql += " AND status='open'"
    elif status == "settled":
        sql += " AND status<>'open'"
    sql += " ORDER BY placed_at DESC"
    with _LOCK:
        rows = conn.execute(sql, args).fetchall()
    return _rows_to_dicts(rows)


def open_bets_with_games(username=None):
    """Open bets that reference a real game id — the settleable ones."""
    conn = get_conn()
    sql = ("SELECT * FROM bets WHERE status='open' "
           "AND game_id IS NOT NULL AND game_id <> ''")
    args = []
    if username:
        sql += " AND username=?"
        args.append(username)
    with _LOCK:
        rows = conn.execute(sql, args).fetchall()
    return _rows_to_dicts(rows)


def history_frame(username):
    """Every bet for a user as a DataFrame, typed for analysis."""
    rows = bets_for(username)
    df = pd.DataFrame(rows, columns=COLUMNS) if rows else pd.DataFrame(columns=COLUMNS)
    if df.empty:
        return df
    df["placed_at"] = pd.to_datetime(df["placed_at"], errors="coerce", format="mixed")
    df["settled_at"] = pd.to_datetime(df["settled_at"], errors="coerce", format="mixed")
    for c in ("stake", "steel_result", "line"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["odds"] = pd.to_numeric(df["odds"], errors="coerce")
    df = df.sort_values("placed_at").reset_index(drop=True)
    # Cumulative P/L only counts settled bets; open stakes aren't losses yet.
    settled_mask = df["status"] != "open"
    df["is_settled"] = settled_mask
    df["running_pl"] = df["steel_result"].where(settled_mask, 0).cumsum()
    return df


def migrate_from_users_json(path="users_db.json"):
    """One-time import of bets that predate this table.

    Runs on every start but only ever inserts ids the table hasn't seen, so
    re-running is a no-op. Returns how many rows it actually added.
    """
    try:
        if not os.path.exists(path):
            return 0
        with open(path, "r") as f:
            users = json.load(f)
    except Exception:
        return 0

    conn = get_conn()
    with _LOCK:
        known = {r["id"] for r in conn.execute("SELECT id FROM bets").fetchall()}
    added = 0
    for uname, user in (users or {}).items():
        for bucket in ("open_bets", "settled_bets"):
            for bet in user.get(bucket) or []:
                bid = bet.get("id")
                if not bid or bid in known:
                    continue
                record_bet(uname, bet)
                known.add(bid)
                added += 1
    return added
