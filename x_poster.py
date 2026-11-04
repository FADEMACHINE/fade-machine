"""Post to the FADE MACHINE X (Twitter) account.

Uses the X API v2 with OAuth 1.0a user context, so posts go out as the account
that owns the access token. Keys come from st.secrets and are all optional:
without them the Post Studio still drafts posts and images, it just can't
publish them.

    X_API_KEY, X_API_SECRET           -> the app's consumer key/secret
    X_ACCESS_TOKEN, X_ACCESS_SECRET   -> @Fade_Machine's user token (read+write)

Nothing here runs on a rerun by itself: every call is made from an explicit
button press in the Post Studio.
"""
import requests
import streamlit as st

TWEET_URL = "https://api.x.com/2/tweets"
MEDIA_UPLOAD_URL = "https://api.x.com/2/media/upload"
MAX_CHARS = 280
_KEYS = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")


def _creds():
    try:
        vals = [st.secrets.get(k) for k in _KEYS]
    except Exception:
        return None
    return vals if all(vals) else None


def is_configured():
    return _creds() is not None


def _auth():
    creds = _creds()
    if not creds:
        return None
    from requests_oauthlib import OAuth1
    return OAuth1(*creds)


def tweet_length(text):
    """X counts every URL as 23 characters; everything else close enough to
    len() for a pre-post check. X still has the final say on submit."""
    import re
    urls = re.findall(r"https?://\S+", text or "")
    stripped = re.sub(r"https?://\S+", "", text or "")
    return len(stripped) + 23 * len(urls)


def _error_text(resp):
    try:
        body = resp.json()
        detail = body.get("detail") or body.get("title") or body.get("errors") or body
    except ValueError:
        detail = resp.text[:300]
    return f"X API {resp.status_code}: {detail}"


def upload_image(png_bytes):
    """Returns (media_id, error)."""
    auth = _auth()
    if auth is None:
        return None, "X keys are not set in st.secrets."
    try:
        resp = requests.post(
            MEDIA_UPLOAD_URL, auth=auth, timeout=30,
            files={"media": ("pick_card.png", png_bytes, "image/png")},
            data={"media_category": "tweet_image", "media_type": "image/png"},
        )
    except requests.RequestException as e:
        return None, f"Image upload failed: {e}"
    if resp.status_code >= 300:
        return None, _error_text(resp)
    body = resp.json()
    data = body.get("data") or {}
    media_id = data.get("id") or body.get("media_id_string")
    return (media_id, None) if media_id else (None, f"Unexpected upload response: {body}")


def post_tweet(text, png_bytes=None):
    """Returns (tweet_url, error). Uploads the image first if one is given."""
    auth = _auth()
    if auth is None:
        return None, "X keys are not set in st.secrets."
    if not (text or "").strip():
        return None, "The post is empty."
    if tweet_length(text) > MAX_CHARS:
        return None, f"The post is {tweet_length(text)} characters; X allows {MAX_CHARS}."
    payload = {"text": text}
    if png_bytes:
        media_id, err = upload_image(png_bytes)
        if err:
            return None, err
        payload["media"] = {"media_ids": [media_id]}
    try:
        resp = requests.post(TWEET_URL, auth=auth, json=payload, timeout=30)
    except requests.RequestException as e:
        return None, f"Post failed: {e}"
    if resp.status_code >= 300:
        return None, _error_text(resp)
    tweet_id = (resp.json().get("data") or {}).get("id")
    return f"https://x.com/Fade_Machine/status/{tweet_id}", None
