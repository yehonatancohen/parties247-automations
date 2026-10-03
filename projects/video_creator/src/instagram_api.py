"""
Instagram publishing via the Instagram API with Instagram Login (graph.instagram.com).

Needs a professional account, a Meta app in development mode with the account added as an
Instagram tester, and a token with instagram_business_basic + instagram_business_content_publish.
No Facebook Page and no app review are involved for the app owner's own account.

Flow for a Reel: create container (video_url must be publicly fetchable) -> poll until FINISHED
-> media_publish.
"""
import json
import os
import re
import time

import requests

from config import Config

BASE = "https://graph.instagram.com"
# A processing ERROR is often transient, and a fresh container minutes later goes through: on 2-3 Oct 2026
# two publishes failed twice 10s apart and then passed on a manual retry a few minutes later. So wait
# longer between attempts; each attempt uses a fresh container.
RETRY_WAITS = (30, 60)         # seconds to wait before the 2nd and the 3rd attempt
PROCESSING_ATTEMPTS = len(RETRY_WAITS) + 1
TOKEN_FILE = None  # tests override; normally one file per target, see _store_path()
REFRESH_AFTER_DAYS = 20          # tokens last 60 days; refresh well before expiry
CAPTION_LIMIT = 2200
HASHTAG_LIMIT = 30
MIN_REEL_SECONDS = 3


class InstagramError(RuntimeError):
    pass


# ----------------------------------------------------------------- token store

TARGETS = ("main", "test")


def resolve_target(target: str | None = None) -> str:
    target = target or Config.IG_TARGET
    if target not in TARGETS:
        raise InstagramError(f"Unknown Instagram account '{target}'; use one of {TARGETS}.")
    return target


def is_configured(target: str | None = None) -> bool:
    return bool(_seed_token(resolve_target(target)) or _load_store(resolve_target(target)).get("access_token"))


def _store_path(target: str) -> str:
    return TOKEN_FILE or os.path.join(Config.OUTPUT_DIR, f"ig_token_{target}.json")


def _seed_token(target: str) -> str:
    return Config.IG_TEST_ACCESS_TOKEN if target == "test" else Config.IG_ACCESS_TOKEN


def _load_store(target: str) -> dict:
    try:
        with open(_store_path(target), "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_store(target: str, token: str):
    path = _store_path(target)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"access_token": token, "refreshed_at": time.time()}, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _token(target: str | None = None) -> str:
    target = resolve_target(target)
    token = _load_store(target).get("access_token") or _seed_token(target)
    if not token:
        raise InstagramError(f"Instagram account '{target}' is not configured: its access token is missing.")
    return token


def _redact(text: str) -> str:
    return re.sub(r"(access_token=)[^&\s'\"]+", r"\1***", str(text))


def _call(method: str, path: str, params: dict | None = None, token: str | None = None,
          target: str | None = None) -> dict:
    """One Graph call. Errors are raised as InstagramError with the token scrubbed."""
    params = dict(params or {})
    params["access_token"] = token or _token(target)
    url = path if path.startswith("http") else f"{BASE}/{Config.IG_GRAPH_VERSION}/{path.lstrip('/')}"
    try:
        resp = requests.request(method, url, params=params if method == "GET" else None,
                                data=params if method != "GET" else None, timeout=60)
    except requests.RequestException as e:
        raise InstagramError(f"Network error talking to Instagram: {_redact(e)}") from None
    try:
        data = resp.json()
    except ValueError:
        raise InstagramError(f"Instagram returned non-JSON (HTTP {resp.status_code}).") from None
    if resp.status_code >= 400 or "error" in data:
        err = data.get("error", {})
        raise InstagramError(
            f"Instagram API error (HTTP {resp.status_code}): {_redact(err.get('message', data))}"
            + (f" [code {err['code']}]" if "code" in err else "")
        )
    return data


def refresh_token_if_due(target: str | None = None) -> bool:
    """Swap the stored token for a fresh 60-day one when it is older than REFRESH_AFTER_DAYS."""
    target = resolve_target(target)
    store = _load_store(target)
    age_days = (time.time() - store.get("refreshed_at", 0)) / 86400
    if store and age_days < REFRESH_AFTER_DAYS:
        return False
    current = store.get("access_token") or _seed_token(target)
    if not current:
        return False
    data = _call("GET", f"{BASE}/refresh_access_token",
                 {"grant_type": "ig_refresh_token"}, token=current)
    _save_store(target, data["access_token"])
    return True


# ------------------------------------------------------------------- publishing

def whoami(target: str | None = None) -> dict:
    data = _call("GET", "me", {"fields": "user_id,username,account_type"}, target=target)
    return {"user_id": str(data.get("user_id") or data.get("id")), "username": data.get("username"),
            "account_type": data.get("account_type")}


def validate_caption(caption: str):
    if len(caption) > CAPTION_LIMIT:
        raise InstagramError(f"Caption is {len(caption)} chars; Instagram allows {CAPTION_LIMIT}.")
    if len(re.findall(r"#\w+", caption)) > HASHTAG_LIMIT:
        raise InstagramError(f"Caption has more than {HASHTAG_LIMIT} hashtags.")


def _wait_until_processed(container: str, target: str, timeout: int):
    deadline = time.time() + timeout
    while True:
        status = _call("GET", container, {"fields": "status_code,status"}, target=target)
        code = status.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise InstagramError(f"Instagram could not process the video ({code}); full response: "
                                 f"{json.dumps(status, ensure_ascii=False)}")
        if time.time() > deadline:
            raise InstagramError("Timed out waiting for Instagram to process the video.")
        time.sleep(5)


def publish_reel(video_url: str, caption: str, duration: float | None = None,
                 share_to_feed: bool = True, timeout: int = 300, target: str | None = None) -> dict:
    """
    Publish a Reel and return {'media_id', 'permalink', 'account', 'target'}. Meta fetches video_url, so it
    must be a public https URL. (Resumable upload is not offered by graph.instagram.com: it answers
    "The parameter video_url is required".) Processing takes anywhere from ~30s to a few minutes and
    occasionally ends in a transient ERROR, so retries with a fresh container are built in (RETRY_WAITS).
    """
    if not (video_url or "").startswith("https://"):
        raise InstagramError("video_url must be a public https URL (set PUBLIC_BASE_URL).")
    if duration is not None and duration < MIN_REEL_SECONDS:
        raise InstagramError(f"Reels must be at least {MIN_REEL_SECONDS}s (this one is {duration:.1f}s).")
    validate_caption(caption)

    target = resolve_target(target)
    refresh_token_if_due(target)
    account = whoami(target)
    user_id = account["user_id"]

    container = None
    for attempt in range(1, PROCESSING_ATTEMPTS + 1):
        container = _call("POST", f"{user_id}/media", {
            "media_type": "REELS", "video_url": video_url, "caption": caption,
            "share_to_feed": "true" if share_to_feed else "false",
        }, target=target)["id"]
        try:
            _wait_until_processed(container, target, timeout)
            break
        except InstagramError as e:
            if attempt == PROCESSING_ATTEMPTS or "could not process" not in str(e):
                raise InstagramError(f"{e} (after {attempt} attempt(s))") from None
            time.sleep(RETRY_WAITS[attempt - 1])

    media_id = _call("POST", f"{user_id}/media_publish", {"creation_id": container}, target=target)["id"]
    try:
        permalink = _call("GET", media_id, {"fields": "permalink"}, target=target).get("permalink")
    except InstagramError:
        permalink = None  # published fine; the link is a nicety
    return {"media_id": media_id, "permalink": permalink, "account": account["username"], "target": target}
