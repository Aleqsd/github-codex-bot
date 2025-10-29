import os
import requests
import openai
from fastapi import FastAPI, Request
from dotenv import load_dotenv
import logging

load_dotenv()

# --- Logging setup ---
log_file_path = os.path.join(os.path.dirname(__file__), "github-codex-bot.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(log_file_path), logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

app = FastAPI()

# --- Environment variables ---
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WATCH_USER = os.getenv("WATCH_USER", "GROBimbo")
REPO = os.getenv("REPO", "Aleqsd/EDH-PodLog")
PORT = int(os.getenv("PORT", 8082))

# Pushover config
PUSHOVER_USER_KEY = os.getenv("PUSHOVER_USER_KEY")
PUSHOVER_API_TOKEN = os.getenv("PUSHOVER_API_TOKEN")

openai.api_key = OPENAI_API_KEY


# --------------- HELPERS ---------------


def notify_pushover(issue_title: str, issue_number: int, message: str):
    """Send push notification via Pushover with contextual GitHub issue link."""
    if not (PUSHOVER_USER_KEY and PUSHOVER_API_TOKEN):
        logger.warning("⚠️ Pushover not configured, skipping notification.")
        return
    issue_url = f"https://github.com/{REPO}/issues/{issue_number}"
    try:
        requests.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token": PUSHOVER_API_TOKEN,
                "user": PUSHOVER_USER_KEY,
                "title": issue_title,
                "message": message,
                "url": issue_url,
                "url_title": f"View issue #{issue_number}",
            },
            timeout=5,
        )
        logger.info("📱 Pushover notification sent.")
    except Exception as e:
        logger.error(f"❌ Pushover notification failed: {e}")


def post_github_comment(issue_number: int, issue_title: str, body: str):
    """Post a comment to a GitHub issue."""
    url = f"https://api.github.com/repos/{REPO}/issues/{issue_number}/comments"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    data = {"body": body}
    r = requests.post(url, json=data, headers=headers)
    if r.status_code not in [200, 201]:
        logger.error(f"❌ Failed to post comment: {r.status_code} {r.text}")
    else:
        msg = f"✅ Comment posted to issue #{issue_number}"
        logger.info(msg)
        notify_pushover(issue_title, issue_number, msg)


def generate_codex_prompt(issue_text: str) -> str:
    """Ask OpenAI to generate a Codex-ready prompt."""
    system_prompt = (
        "You are an assistant helping a developer generate a ready-to-use prompt "
        "for Codex CLI, which will implement the requested feature in the GitHub repository "
        "'Aleqsd/EDH-PodLog'. This repository manages Magic: The Gathering decks, users, matches, "
        "and deck synchronization.\n\n"
        "Your task:\n"
        "- Rewrite the Product Owner message into a clear, comprehensive, and Codex-ready prompt.\n"
        "- Preserve every requirement, constraint, data detail, and acceptance criterion from the Product Owner message.\n"
        "- Expand terse descriptions so the resulting prompt is very detailed, leaving no ambiguity for the implementer.\n"
        "- Keep it fully in English.\n"
        "- Focus on what needs to be implemented (new features, changes, endpoints, data model updates).\n"
        "- Avoid repetition or irrelevant context beyond what is necessary to preserve meaning.\n"
        "- Output only the Codex prompt, ready to be pasted in terminal.\n"
        "\nExample output:\n"
        "Implement a new FastAPI endpoint `POST /decks/import` allowing users to import a deck from Moxfield. "
        "Use the existing `Deck` model in `models/deck.py`. Validate user authentication via `get_current_user()`. "
        "On success, return the new deck as JSON.\n\n"
        "---\n\n"
        "Now rewrite this message from the Product Owner into such a Codex-ready prompt without omitting any detail."
    )

    try:
        completion = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": issue_text},
            ],
            temperature=0.4,
        )
        return completion.choices[0].message.content.strip()  # type: ignore
    except Exception as e:
        logger.error(f"❌ OpenAI API error: {e}")
        return "⚠️ Failed to generate Codex prompt."


# --------------- WEBHOOK ENDPOINT ---------------


@app.post("/github-webhook-codex")
async def github_webhook(request: Request):
    payload = await request.json()
    event = request.headers.get("X-GitHub-Event", "ping")

    logger.info(f"📬 Received event: {event}")

    if event not in ["issues", "issue_comment"]:
        return {"msg": "ignored"}

    sender = payload.get("sender", {}).get("login", "")
    issue = payload.get("issue", {})
    issue_number = issue.get("number")
    issue_title = issue.get("title", "")
    body = issue.get("body", "")
    comment = payload.get("comment", {}).get("body")

    # Filter: only from WATCH_USER
    if sender != WATCH_USER:
        logger.info(f"🙅 Ignored event from {sender}")
        return {"msg": "ignored"}

    # Determine text source
    text = comment if comment else f"{issue_title}\n\n{body}"
    logger.info(f"🧠 Processing issue #{issue_number} from {sender}")

    codex_prompt = generate_codex_prompt(text)

    comment_body = f"🤖 **Prompt ready for Codex:**\n\n```\n{codex_prompt}\n```"
    post_github_comment(issue_number, issue_title, comment_body)

    return {"msg": "processed"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=PORT)
