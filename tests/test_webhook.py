import hashlib
import hmac
import json

from fastapi.testclient import TestClient

import bot


def _sign_payload(payload: dict) -> tuple[str, bytes]:
    body = json.dumps(payload).encode("utf-8")
    digest = hmac.new(bot.GITHUB_WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    header = f"sha256={digest}"
    return header, body


def test_github_webhook_rejects_invalid_signature():
    client = TestClient(bot.app)
    payload = {"action": "opened"}
    response = client.post(
        "/github-webhook-codex",
        content=json.dumps(payload),
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": "sha256=deadbeef",
        },
    )
    assert response.status_code == 401


def test_github_webhook_ignores_unwatched_sender(monkeypatch):
    client = TestClient(bot.app)
    payload = {
        "action": "opened",
        "sender": {"login": "someone-else"},
        "issue": {"number": 3, "title": "Not our issue", "body": "ignore me"},
    }
    signature, body = _sign_payload(payload)

    observed = {}
    monkeypatch.setattr(bot, "post_github_comment", lambda *args, **kwargs: observed.setdefault("called", True))

    response = client.post(
        "/github-webhook-codex",
        content=body,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"msg": "ignored"}
    assert observed == {}


def test_github_webhook_posts_comment_for_valid_issue(monkeypatch):
    client = TestClient(bot.app)
    payload = {
        "action": "opened",
        "sender": {"login": bot.WATCH_USER},
        "issue": {"number": 8, "title": "Deck stats", "body": "Please add stats"},
    }
    signature, body = _sign_payload(payload)

    monkeypatch.setattr(bot, "generate_codex_prompt", lambda text: "Preserved Requirements:\n- Requirement A\n\nPrompt: Do something")

    posted = {}

    def fake_post_comment(issue_number, issue_title, comment_body):
        posted["issue_number"] = issue_number
        posted["issue_title"] = issue_title
        posted["comment_body"] = comment_body

    monkeypatch.setattr(bot, "post_github_comment", fake_post_comment)
    monkeypatch.setattr(bot, "notify_pushover", lambda *args, **kwargs: None)

    response = client.post(
        "/github-webhook-codex",
        content=body,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"msg": "processed"}
    assert posted["issue_number"] == 8
    assert posted["issue_title"] == "Deck stats"
    assert posted["comment_body"].startswith("🤖 **Prompt ready for Codex:**\n\n```\nPreserved Requirements:")


def test_github_webhook_ignores_non_opened_issue_actions(monkeypatch):
    client = TestClient(bot.app)
    payload = {
        "action": "labeled",
        "sender": {"login": bot.WATCH_USER},
        "issue": {"number": 11, "title": "Deck stats", "body": "Please add stats"},
    }
    signature, body = _sign_payload(payload)

    observed = {}
    monkeypatch.setattr(bot, "post_github_comment", lambda *args, **kwargs: observed.setdefault("called", True))

    response = client.post(
        "/github-webhook-codex",
        content=body,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"msg": "ignored"}
    assert observed == {}


def test_github_webhook_posts_comment_for_new_issue_comment(monkeypatch):
    client = TestClient(bot.app)
    payload = {
        "action": "created",
        "sender": {"login": bot.WATCH_USER},
        "issue": {"number": 9, "title": "Deck sync", "body": "Sync request"},
        "comment": {"body": "I have more details"},
    }
    signature, body = _sign_payload(payload)

    monkeypatch.setattr(bot, "generate_codex_prompt", lambda text: "Preserved Requirements:\n- Requirement B\n\nPrompt: Handle sync")

    posted = {}

    def fake_post_comment(issue_number, issue_title, comment_body):
        posted["issue_number"] = issue_number
        posted["issue_title"] = issue_title
        posted["comment_body"] = comment_body

    monkeypatch.setattr(bot, "post_github_comment", fake_post_comment)
    monkeypatch.setattr(bot, "notify_pushover", lambda *args, **kwargs: None)

    response = client.post(
        "/github-webhook-codex",
        content=body,
        headers={
            "X-GitHub-Event": "issue_comment",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"msg": "processed"}
    assert posted["issue_number"] == 9
    assert posted["issue_title"] == "Deck sync"
    assert posted["comment_body"].startswith("🤖 **Prompt ready for Codex:**\n\n```\nPreserved Requirements:")


def test_github_webhook_ignores_non_created_comment_actions(monkeypatch):
    client = TestClient(bot.app)
    payload = {
        "action": "edited",
        "sender": {"login": bot.WATCH_USER},
        "issue": {"number": 10, "title": "Deck sync", "body": "Sync request"},
        "comment": {"body": "Edited details"},
    }
    signature, body = _sign_payload(payload)

    observed = {}
    monkeypatch.setattr(bot, "post_github_comment", lambda *args, **kwargs: observed.setdefault("called", True))

    response = client.post(
        "/github-webhook-codex",
        content=body,
        headers={
            "X-GitHub-Event": "issue_comment",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"msg": "ignored"}
    assert observed == {}
