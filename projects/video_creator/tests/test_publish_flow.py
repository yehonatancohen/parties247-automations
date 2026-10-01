"""Instagram publishing + approval gate, with all network calls faked (nothing touches Instagram)."""
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from config import Config  # noqa: E402
import instagram_api as ig  # noqa: E402
import pipeline  # noqa: E402
import publisher  # noqa: E402

TOKEN = "IGQV-secret-token-123"


class FakeResp:
    def __init__(self, data, status=200):
        self._d, self.status_code = data, status

    def json(self):
        return self._d


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "JOBS_DIR", str(tmp_path / "jobs"))
    os.makedirs(Config.JOBS_DIR)
    monkeypatch.setattr(Config, "IG_ACCESS_TOKEN", TOKEN)
    monkeypatch.setattr(Config, "IG_TARGET", "main")
    monkeypatch.setattr(Config, "PUBLIC_BASE_URL", "https://video.example.com")
    monkeypatch.setattr(Config, "PUBLISH_MODE", "instagram")
    monkeypatch.setattr(Config, "APPROVAL_CODE_REQUIRED", True)
    monkeypatch.setattr(ig, "TOKEN_FILE", str(tmp_path / "ig_token.json"))
    monkeypatch.setattr(time, "sleep", lambda s: None)
    sent = []
    monkeypatch.setattr(publisher, "send_text", lambda t: sent.append(t))
    return sent


def make_job(status="ready", duration=15.0):
    jid = "abc123abc123"
    os.makedirs(pipeline.job_dir(jid), exist_ok=True)
    video = os.path.join(pipeline.job_dir(jid), "final.mp4")
    with open(video, "wb") as f:
        f.write(b"x" * 2048)
    job = {"id": jid, "video_path": video, "status": status, "created_at": time.time(), "title": "title", "body": "body",
           "caption": "hook\n#a #b", "preview_token": "tok", "media": {"duration": duration}, "warnings": []}
    pipeline._save(job)
    return jid


def fake_graph(monkeypatch, calls, statuses=("IN_PROGRESS", "FINISHED"), fail_publish=False):
    seq = iter(statuses)

    def request(method, url, params=None, data=None, timeout=None, headers=None):
        sent = params if method == "GET" else data
        calls.append((method, url, dict(sent)))
        assert sent["access_token"]  # always authenticated
        if url.endswith("/me"):
            return FakeResp({"user_id": "1784", "username": "parties_24.7"})
        if url.endswith("/1784/media"):
            return FakeResp({"id": "container1"})
        if url.endswith("/container1"):
            return FakeResp({"status_code": next(seq)})
        if url.endswith("/1784/media_publish"):
            if fail_publish:
                return FakeResp({"error": {"message": f"boom access_token={sent['access_token']}", "code": 190}}, 400)
            return FakeResp({"id": "media9"})
        if url.endswith("/media9"):
            return FakeResp({"permalink": "https://instagram.com/reel/xyz"})
        if url.endswith("refresh_access_token"):
            return FakeResp({"access_token": "NEWTOKEN", "expires_in": 5184000})
        raise AssertionError(f"unexpected call {method} {url}")

    monkeypatch.setattr(ig.requests, "request", request)


# ---------------------------------------------------------------- instagram_api

def test_publish_reel_happy_path(env, monkeypatch):
    calls = []
    fake_graph(monkeypatch, calls)
    out = ig.publish_reel("https://video.example.com/preview/x.mp4", "hi #a", duration=10)
    assert out == {"media_id": "media9", "permalink": "https://instagram.com/reel/xyz", "account": "parties_24.7", "target": "main"}
    create = next(c for c in calls if c[1].endswith("/1784/media"))
    assert create[2]["media_type"] == "REELS" and create[2]["video_url"].startswith("https://")
    assert create[2]["caption"] == "hi #a" and create[2]["share_to_feed"] == "true"
    order = [c[1].rsplit("/", 1)[-1] for c in calls if c[0] == "POST"]
    assert order == ["media", "media_publish"]


@pytest.mark.parametrize("kwargs,msg", [
    (dict(video_url="http://x/y.mp4", caption="c"), "https"),
    (dict(video_url="https://x/y.mp4", caption="c", duration=2), "at least"),
    (dict(video_url="https://x/y.mp4", caption="c" * 2300), "2200"),
    (dict(video_url="https://x/y.mp4", caption=" ".join(f"#t{i}" for i in range(31))), "hashtags"),
])
def test_publish_reel_validation(env, monkeypatch, kwargs, msg):
    fake_graph(monkeypatch, [])
    with pytest.raises(ig.InstagramError, match=msg):
        ig.publish_reel(**kwargs)


def test_processing_error_and_token_never_leaks(env, monkeypatch):
    fake_graph(monkeypatch, [], statuses=("ERROR", "ERROR"))
    with pytest.raises(ig.InstagramError, match="could not process"):
        ig.publish_reel("https://x/y.mp4", "c", duration=10)

    fake_graph(monkeypatch, [], fail_publish=True)
    with pytest.raises(ig.InstagramError) as e:
        ig.publish_reel("https://x/y.mp4", "c", duration=10)
    assert TOKEN not in str(e.value) and "***" in str(e.value)


def test_token_refresh_only_when_due(env, monkeypatch):
    calls = []
    fake_graph(monkeypatch, calls)
    assert ig.refresh_token_if_due() is True            # no store yet -> seed token gets refreshed
    assert ig._token() == "NEWTOKEN"
    assert ig.refresh_token_if_due() is False           # fresh -> no call
    assert sum("refresh_access_token" in c[1] for c in calls) == 1


def test_processing_error_is_retried_with_a_fresh_container(env, monkeypatch):
    calls = []
    fake_graph(monkeypatch, calls, statuses=("ERROR", "FINISHED"))
    out = ig.publish_reel("https://x/y.mp4", "c", duration=10)
    assert out["media_id"] == "media9"
    assert sum(c[1].endswith("/1784/media") for c in calls) == 2      # two containers were created
    assert sum(c[1].endswith("/media_publish") for c in calls) == 1   # but only one post


def test_persistent_error_reports_full_detail_and_never_publishes(env, monkeypatch):
    calls = []
    fake_graph(monkeypatch, calls, statuses=("ERROR", "ERROR"))
    with pytest.raises(ig.InstagramError, match=r"full response.*status_code.*after 2 attempt"):
        ig.publish_reel("https://x/y.mp4", "c", duration=10)
    assert not any(c[1].endswith("/media_publish") for c in calls)


# -------------------------------------------------------------- approval gate

def code_from(sent):
    return next(w for w in sent[-1].split() if w.isdigit() and len(w) == 6)


def test_publish_requires_code(env, monkeypatch):
    jid = make_job()
    fake_graph(monkeypatch, [])
    with pytest.raises(RuntimeError, match="Approval required"):
        publisher.publish(jid)                           # never requested
    r = publisher.request_publish(jid)
    assert r["approval_needed"] and len(env) == 1
    good = code_from(env)
    with pytest.raises(RuntimeError, match="Wrong approval code"):
        publisher.publish(jid, "000000" if good != "000000" else "111111")
    with pytest.raises(RuntimeError, match="Wrong approval code"):
        publisher.publish(jid, None)
    assert pipeline.get_job(jid)["status"] == "ready"


def test_correct_code_publishes_once(env, monkeypatch):
    jid = make_job()
    fake_graph(monkeypatch, [])
    publisher.request_publish(jid)
    out = publisher.publish(jid, code_from(env))
    assert out["mode"] == "instagram" and out["media_id"] == "media9"
    job = pipeline.get_job(jid)
    assert job["status"] == "published" and "approval" not in job
    with pytest.raises(RuntimeError, match="already published"):
        publisher.publish(jid, "123456")
    assert "https://instagram.com/reel/xyz" in env[-1]   # owner is told it is live


def test_code_locks_after_five_wrong_attempts(env, monkeypatch):
    jid = make_job()
    fake_graph(monkeypatch, [])
    publisher.request_publish(jid)
    good = code_from(env)
    bad = "999999" if good != "999999" else "888888"
    for _ in range(5):
        with pytest.raises(RuntimeError, match="Wrong approval code"):
            publisher.publish(jid, bad)
    with pytest.raises(RuntimeError, match="Too many wrong codes"):
        publisher.publish(jid, good)                     # even the right code is refused now


def test_code_expires(env, monkeypatch):
    jid = make_job()
    fake_graph(monkeypatch, [])
    publisher.request_publish(jid)
    job = pipeline.get_job(jid)
    job["approval"]["expires"] = time.time() - 1
    pipeline._save(job)
    with pytest.raises(RuntimeError, match="expired"):
        publisher.publish(jid, code_from(env))


def test_failed_post_reverts_to_ready_and_keeps_error(env, monkeypatch):
    jid = make_job()
    fake_graph(monkeypatch, [], fail_publish=True)
    publisher.request_publish(jid)
    with pytest.raises(ig.InstagramError):
        publisher.publish(jid, code_from(env))
    job = pipeline.get_job(jid)
    assert job["status"] == "ready" and "boom" in job["publish_error"] and TOKEN not in job["publish_error"]


def test_refuses_unrendered_jobs(env):
    jid = make_job(status="rendering")
    with pytest.raises(RuntimeError, match="not ready"):
        publisher.publish(jid, "123456")
    with pytest.raises(RuntimeError, match="not ready"):
        publisher.request_publish(jid)


def test_manual_mode_needs_no_code(env, monkeypatch):
    monkeypatch.setattr(Config, "PUBLISH_MODE", "manual")
    jid = make_job()
    monkeypatch.setattr(publisher, "send_to_telegram", lambda job: {"mode": "manual", "sent_to": "telegram"})
    assert publisher.request_publish(jid)["approval_needed"] is False
    assert publisher.publish(jid)["mode"] == "manual"
    assert pipeline.get_job(jid)["status"] == "handed_off"


def test_approval_message_names_the_target_account(env, monkeypatch):
    jid = make_job()
    fake_graph(monkeypatch, [])
    r = publisher.request_publish(jid)
    assert r["target_account"] == "@parties_24.7" and "@parties_24.7" in env[-1]


def test_test_target_uses_its_own_token_and_store(env, monkeypatch, tmp_path):
    monkeypatch.setattr(ig, "TOKEN_FILE", None)           # use the per-target default path
    monkeypatch.setattr(Config, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(Config, "IG_TARGET", "test")
    monkeypatch.setattr(Config, "IG_TEST_ACCESS_TOKEN", "TEST-TOKEN")
    calls = []
    fake_graph(monkeypatch, calls)
    assert ig._token() == "TEST-TOKEN"                    # never the main account's token
    ig.refresh_token_if_due()
    assert os.path.basename(ig._store_path("test")) == "ig_token_test.json" and os.path.exists(ig._store_path("test"))
    monkeypatch.setattr(Config, "IG_TARGET", "main")
    assert ig._token() == TOKEN                           # main target unaffected by the test store


def test_unconfigured_target_fails_clearly(env, monkeypatch):
    monkeypatch.setattr(Config, "IG_TEST_ACCESS_TOKEN", "")
    with pytest.raises(ig.InstagramError, match="'test' is not configured"):
        ig._token("test")
    with pytest.raises(ig.InstagramError, match="Unknown Instagram account"):
        ig._token("prod")


# ------------------------------------------------- two accounts, chosen per approval

def test_each_account_publishes_with_its_own_token(env, monkeypatch):
    monkeypatch.setattr(Config, "IG_TEST_ACCESS_TOKEN", "TEST-TOKEN")
    seen = []
    base_request = None

    def request(method, url, params=None, data=None, timeout=None, headers=None):
        sent = params if method == "GET" else data
        seen.append(sent["access_token"])
        if url.endswith("/me"):
            who = "cheetah" if sent["access_token"].startswith("TEST") else "parties_24.7"
            return FakeResp({"user_id": "1", "username": who})
        if url.endswith("refresh_access_token"):
            return FakeResp({"access_token": sent["access_token"], "expires_in": 1})
        if url.endswith("/media"):
            return FakeResp({"id": "c1"})
        if url.endswith("/c1"):
            return FakeResp({"status_code": "FINISHED"})
        if url.endswith("/media_publish"):
            return FakeResp({"id": "m1"})
        return FakeResp({"permalink": "https://instagram.com/reel/t"})

    monkeypatch.setattr(ig.requests, "request", request)

    jid = make_job()
    r = publisher.request_publish(jid, "test")
    assert r["target_account"] == "@cheetah" and "@cheetah (test)" in env[-1]
    out = publisher.publish(jid, code_from(env))
    assert out["account"] == "cheetah" and out["target"] == "test"
    assert set(seen) == {"TEST-TOKEN"}                    # the main account's token was never used


def test_approval_is_bound_to_the_account_the_owner_saw(env, monkeypatch):
    monkeypatch.setattr(Config, "IG_TEST_ACCESS_TOKEN", "TEST-TOKEN")
    jid = make_job()
    fake_graph(monkeypatch, [])
    publisher.request_publish(jid, "test")
    with pytest.raises(RuntimeError, match="approval was for account 'test', not 'main'"):
        publisher.publish(jid, code_from(env), account="main")
    assert pipeline.get_job(jid)["status"] == "ready"


def test_request_refused_for_unconfigured_or_unknown_account(env, monkeypatch):
    monkeypatch.setattr(Config, "IG_TEST_ACCESS_TOKEN", "")
    jid = make_job()
    fake_graph(monkeypatch, [])
    with pytest.raises(RuntimeError, match="'test' is not configured"):
        publisher.request_publish(jid, "test")
    with pytest.raises(ig.InstagramError, match="Unknown Instagram account"):
        publisher.request_publish(jid, "evil")
    assert env == []                                      # no code is sent for a refused request
