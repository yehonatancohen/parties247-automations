"""
Hand-off of finished videos. Only acts on jobs whose render is verified (status 'ready').

PUBLISH_MODE is a server-side setting (env), never a tool parameter, so a calling model cannot
switch itself from "hand it to the owner" to "post it publicly".

  manual     send the video + caption to the owner on Telegram (no approval code needed).
  instagram  post a Reel through the Instagram API. Needs a one-time code that request_publish()
             sends to the owner on Telegram and that the owner types back in the chat, so the
             model cannot approve its own post.
"""
import hashlib
import hmac
import os
import secrets
import time

import requests

import instagram_api
import pipeline
from config import Config

TELEGRAM_VIDEO_LIMIT = 50 * 1024 * 1024  # Bot API: sendVideo max 50MB
TELEGRAM_CAPTION_LIMIT = 1024
APPROVAL_TTL = 30 * 60
APPROVAL_MAX_ATTEMPTS = 5


# --------------------------------------------------------------------- telegram

def _telegram_target() -> tuple[str, int]:
    token = Config.TELEGRAM_TOKEN
    users = Config.get_allowed_user_ids()
    if not token or not users:
        raise RuntimeError("TELEGRAM_TOKEN / ALLOWED_USER_ID not configured.")
    return token, users[0]


def _tg(method: str, **kwargs):
    token, _ = _telegram_target()
    resp = requests.post(f"https://api.telegram.org/bot{token}/{method}", timeout=300, **kwargs)
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method} failed: {data.get('description', 'unknown error')}")
    return data["result"]


def send_text(text: str):
    _, chat_id = _telegram_target()
    _tg("sendMessage", data={"chat_id": chat_id, "text": text})


def send_to_telegram(job: dict) -> dict:
    """Send the finished video + full caption to the owner on Telegram."""
    _, chat_id = _telegram_target()
    path = job["video_path"]
    caption = job["caption"]

    if os.path.getsize(path) > TELEGRAM_VIDEO_LIMIT:
        raise RuntimeError("Video is over Telegram's 50MB limit; shorten the source clip.")

    short = caption if len(caption) <= TELEGRAM_CAPTION_LIMIT else None
    with open(path, "rb") as f:
        _tg("sendVideo",
            data={"chat_id": chat_id, "caption": short or f"🎬 {job['title']}",
                  "width": Config.VIDEO_SIZE[0], "height": Config.VIDEO_SIZE[1],
                  "supports_streaming": "true"},
            files={"video": f})
    if short is None:
        send_text(caption)
    return {"mode": "manual", "sent_to": "telegram"}


# ------------------------------------------------------------- approval handling

def _code_hash(code: str, job_id: str) -> str:
    return hashlib.sha256(f"{job_id}:{code}".encode()).hexdigest()


def request_publish(job_id: str, account: str | None = None) -> dict:
    """
    Send the owner a one-time approval code on Telegram (instagram mode only). The message names the
    Instagram account the post will go to, and the approval is bound to that account, so the owner
    verifies the destination before typing the code.
    """
    job = pipeline.get_job(job_id)
    if job["status"] != "ready":
        raise RuntimeError(f"Job is '{job['status']}', not ready.")
    if Config.PUBLISH_MODE != "instagram" or not Config.APPROVAL_CODE_REQUIRED:
        return {"approval_needed": False,
                "message": "No approval code is needed in the current mode; call publish_video directly."}

    target = instagram_api.resolve_target(account)
    if not instagram_api.is_configured(target):
        raise RuntimeError(f"Instagram account '{target}' is not configured on the server.")
    # If the account cannot be identified, refuse: the owner must see the real destination.
    handle = "@" + instagram_api.whoami(target)["username"]

    code = f"{secrets.randbelow(10**6):06d}"
    job["approval"] = {"hash": _code_hash(code, job_id), "expires": time.time() + APPROVAL_TTL,
                       "attempts": 0, "account": target}
    pipeline._save(job)
    send_text(f"🔐 קוד אישור לפרסום ל-Instagram: {code}\n"
              f"חשבון יעד: {handle} ({target})\n"
              f"סרטון: {job['title']}\n"
              f"תקף ל-{APPROVAL_TTL // 60} דקות. תמסור אותו בצ'אט רק אם אתה מאשר לפרסם.")
    return {"approval_needed": True,
            "target_account": handle,
            "message": "A 6-digit approval code was sent to the owner on Telegram. Ask the owner to type it "
                       "here, then call publish_video(job_id, approval_code). Never guess or reuse a code."}


def _check_code(job: dict, code: str | None):
    approval = job.get("approval")
    if not approval:
        raise RuntimeError("Approval required: call request_publish_approval first.")
    if time.time() > approval["expires"]:
        raise RuntimeError("The approval code expired. Call request_publish_approval again.")
    if approval["attempts"] >= APPROVAL_MAX_ATTEMPTS:
        raise RuntimeError("Too many wrong codes. Call request_publish_approval again.")
    ok = bool(code) and hmac.compare_digest(approval["hash"], _code_hash(str(code).strip(), job["id"]))
    if not ok:
        approval["attempts"] += 1
        pipeline._save(job)
        raise RuntimeError("Wrong approval code.")


# ------------------------------------------------------------------------ publish

def publish(job_id: str, approval_code: str | None = None, account: str | None = None) -> dict:
    job = pipeline.get_job(job_id)
    if job["status"] == "published":
        raise RuntimeError("This job was already published.")
    if job["status"] not in ("ready", "handed_off"):
        raise RuntimeError(f"Job is '{job['status']}', not ready. Wait for status 'ready' before publishing.")

    mode = Config.PUBLISH_MODE
    if mode == "manual":
        result = send_to_telegram(job)
        job["status"] = "handed_off"
    elif mode == "instagram":
        if Config.APPROVAL_CODE_REQUIRED:
            _check_code(job, approval_code)
            target = job["approval"]["account"]          # the account the owner saw on Telegram
            if account and account != target:
                raise RuntimeError(f"The approval was for account '{target}', not '{account}'. "
                                   "Request a new approval for the other account.")
        else:
            target = instagram_api.resolve_target(account)
        previous = job["status"]
        job["status"] = "publishing"          # blocks a concurrent double-post
        pipeline._save(job)
        try:
            posted = instagram_api.publish_reel(
                pipeline.preview_url(job), job["caption"],
                duration=(job.get("media") or {}).get("duration"), target=target)
        except Exception as e:
            job["status"], job["publish_error"] = previous, str(e)[:500]
            pipeline._save(job)
            raise
        job.pop("approval", None)
        result = {"mode": "instagram", **posted}
        job["status"] = "published"
        try:
            send_text(f"✅ פורסם ב-@{posted.get('account')}: {posted.get('permalink') or posted['media_id']}")
        except Exception:
            pass                               # the post is live; a failed notification is not an error
    else:
        raise RuntimeError(f"Unknown PUBLISH_MODE: {mode}")

    job["publish"] = result
    pipeline._save(job)
    return result
