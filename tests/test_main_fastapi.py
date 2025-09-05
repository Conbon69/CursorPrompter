import json
import os
from typing import List, Tuple

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    # Minimal env to avoid surprises during import
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    # Do not require external services for tests
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    yield


@pytest.fixture
def app_module(monkeypatch, tmp_path):
    # Import the app and monkeypatch file paths to temp files to avoid touching repo files
    import importlib
    mod = importlib.import_module("main_fastapi")

    results_file = tmp_path / "results.jsonl"
    selection_file = tmp_path / "selected_ideas.json"
    saved_file = tmp_path / "saved_ideas.json"

    monkeypatch.setattr(mod, "RESULTS_FILE", str(results_file), raising=False)
    monkeypatch.setattr(mod, "SELECTION_FILE", str(selection_file), raising=False)
    monkeypatch.setattr(mod, "SAVED_FILE", str(saved_file), raising=False)

    # Ensure quota functions are harmless
    monkeypatch.setattr(mod, "get_daily_usage", lambda _email: 0, raising=False)
    monkeypatch.setattr(mod, "increment_daily_usage", lambda _email: True, raising=False)
    try:
        from fastapi_db_helpers import increment_daily_usage_by_safe
        monkeypatch.setattr(
            mod, "increment_daily_usage_by_safe", lambda _email, _n: True, raising=False
        )
    except Exception:
        pass

    return mod


@pytest.fixture
def client(app_module):
    return TestClient(app_module.app)


def test_home_page_smoke(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Reddit SaaS Idea Finder" in r.text


def test_scrape_requires_subreddits(client):
    r = client.post(
        "/scrape",
        data={"subreddit": "", "posts_per_subreddit": "2", "comments_per_post": "5"},
    )
    assert r.status_code == 200
    assert "Please enter a single subreddit" in r.text


def test_scrape_success_with_mock(client, app_module, monkeypatch):
    # Allow scraping and mock run_pipeline
    monkeypatch.setattr(app_module, "can_user_scrape", lambda _email: (True, 0, 2))

    def fake_run_pipeline(subs: List[str], pps: int, cpp: int):
        results = [
            {
                "meta": {"uuid": "u1", "scraped_at": "2024-01-01T00:00:00Z"},
                "reddit": {
                    "subreddit": subs[0],
                    "url": "https://reddit.com/r/test/1",
                    "title": "Test Post",
                    "id": "r1",
                },
                "analysis": {"problem_description": "P", "confidence_score": 0.8},
                "solution": {"solution_description": "S", "mvp_features": ["F1"]},
                "cursor_playbook": ["Do X", "Do Y"],
            }
        ]
        report = [
            {"title": "Test Post", "url": "https://reddit.com/r/test/1", "status": "Added", "details": "P"}
        ]
        return results, report

    monkeypatch.setattr(app_module, "run_pipeline", fake_run_pipeline)

    r = client.post(
        "/scrape",
        data={"subreddit": "testing", "posts_per_subreddit": "1", "comments_per_post": "2"},
    )
    assert r.status_code == 200
    # Results page content
    assert "Scraping Results" in r.text
    assert "Test Post" in r.text
    assert "Cursor Playbook Prompts" in r.text


def test_verify_flow_pages(client, app_module, monkeypatch):
    # Start page
    r = client.get("/verify")
    assert r.status_code == 200

    # POST /verify creates token and sends email (mocked)
    monkeypatch.setattr(
        app_module, "create_verification_record", lambda email: "tok-123"
    )
    monkeypatch.setattr(
        app_module, "send_verification_email_fastapi", lambda email, token, base: True
    )

    r2 = client.post("/verify", data={"email": "user@example.com"})
    assert r2.status_code == 200
    assert "Verification record" in r2.text or "Verification email" in r2.text

    # Confirm route sets cookie and redirects
    def fake_verify_token(token: str) -> Tuple[bool, str]:
        return True, "user@example.com"

    monkeypatch.setattr(app_module, "verify_token", fake_verify_token)
    monkeypatch.setattr(app_module, "update_last_login", lambda email: None)

    r3 = client.get("/verify/confirm", params={"token": "tok-123"}, allow_redirects=False)
    assert r3.status_code in (302, 307)
    assert r3.headers.get("set-cookie") is not None


def test_api_requires_auth(client):
    r = client.get("/api/ideas")
    assert r.status_code == 401


def test_toggle_saved_status_flow(client, app_module, monkeypatch, tmp_path):
    # Prepare one idea owned by this email
    owner = "me@example.com"
    idea = {
        "meta": {"uuid": "uuid-1", "scraped_at": "2024-01-01T00:00:00Z"},
        "reddit": {
            "subreddit": "test",
            "url": "https://reddit.com/r/test/1",
            "title": "Idea 1",
            "id": "r1",
        },
        "analysis": {"problem_description": "p"},
        "solution": {"solution_description": "s", "mvp_features": ["f"]},
        "cursor_playbook": ["p1"],
        "owner_email": owner,
    }

    # Point files to temp and write the idea
    results_file = app_module.RESULTS_FILE
    with open(results_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(idea) + "\n")

    # Monkeypatch verification to treat user as verified
    monkeypatch.setattr(app_module, "is_email_verified", lambda _e: True)

    # Build a session cookie by calling module creator
    session_token = app_module.create_session_token(owner)
    client.cookies.set(app_module.SESSION_COOKIE_NAME, session_token)

    # Toggle without explicit status (will set to saved)
    r = client.patch(f"/api/ideas/{idea['meta']['uuid']}/status")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("saved", "new")

    # Explicit set to new
    r2 = client.patch(
        f"/api/ideas/{idea['meta']['uuid']}/status", json={"status": "new"}
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "new"


