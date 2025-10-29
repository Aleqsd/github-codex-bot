import bot


class DummyResponse:
    status_code = 201
    text = "ok"


def test_notify_pushover_includes_issue_link(monkeypatch):
    captured = {}

    def fake_post(url, data, timeout):
        captured["url"] = url
        captured["data"] = data
        return DummyResponse()

    monkeypatch.setattr(bot, "PUSHOVER_USER_KEY", "user")
    monkeypatch.setattr(bot, "PUSHOVER_API_TOKEN", "token")
    monkeypatch.setattr(bot.requests, "post", fake_post)

    bot.notify_pushover("Fix critical bug", 42, "Prompt posted")

    assert captured["url"] == "https://api.pushover.net/1/messages.json"
    assert captured["data"]["title"] == "Fix critical bug"
    assert captured["data"]["url"] == f"https://github.com/{bot.REPO}/issues/42"
    assert captured["data"]["url_title"] == "View issue #42"


def test_post_github_comment_notifies_with_issue_details(monkeypatch):
    github_call = {}

    def fake_github_post(url, json, headers):
        github_call["url"] = url
        github_call["json"] = json
        github_call["headers"] = headers
        return DummyResponse()

    notified = {}

    def fake_notify(title, number, message):
        notified["title"] = title
        notified["number"] = number
        notified["message"] = message

    monkeypatch.setattr(bot, "GITHUB_TOKEN", "ghp_test")
    monkeypatch.setattr(bot.requests, "post", fake_github_post)
    monkeypatch.setattr(bot, "notify_pushover", fake_notify)

    bot.post_github_comment(7, "Deck export not working", "body text")

    assert github_call["url"].endswith("/issues/7/comments")
    assert github_call["json"] == {"body": "body text"}
    assert github_call["headers"]["Authorization"] == "token ghp_test"
    assert notified == {
        "title": "Deck export not working",
        "number": 7,
        "message": "✅ Comment posted to issue #7",
    }
