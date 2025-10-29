import hashlib
import hmac
import json
import logging
import os
import time
from typing import Callable, Optional

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request

try:
    from openai import OpenAI
except ModuleNotFoundError as exc:  # pragma: no cover - import guard
    OpenAI = None  # type: ignore[assignment]
    _OPENAI_IMPORT_ERROR = exc
else:
    _OPENAI_IMPORT_ERROR = None

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


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable '{name}' must be set for github-codex-bot.")
    return value


GITHUB_TOKEN = _require_env("GITHUB_TOKEN")
OPENAI_API_KEY = _require_env("OPENAI_API_KEY")
WATCH_USER = _require_env("WATCH_USER")
REPO = _require_env("REPO")
GITHUB_WEBHOOK_SECRET = _require_env("GITHUB_WEBHOOK_SECRET")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
PORT = int(os.getenv("PORT", 8082))
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "5"))
HTTP_MAX_RETRIES = int(os.getenv("HTTP_MAX_RETRIES", "3"))
HTTP_RETRY_BACKOFF_SECONDS = float(os.getenv("HTTP_RETRY_BACKOFF_SECONDS", "0.5"))

# Pushover config
PUSHOVER_USER_KEY = os.getenv("PUSHOVER_USER_KEY")
PUSHOVER_API_TOKEN = os.getenv("PUSHOVER_API_TOKEN")

openai_client = OpenAI(api_key=OPENAI_API_KEY) if OpenAI else None


# --------------- HELPERS ---------------


def _send_with_retries(action_name: str, request_factory: Callable[[], requests.Response]) -> Optional[requests.Response]:
    """Execute an HTTP request with retries and backoff."""
    for attempt in range(1, HTTP_MAX_RETRIES + 1):
        try:
            response = request_factory()
            return response
        except requests.RequestException as exc:
            if attempt < HTTP_MAX_RETRIES:
                logger.warning(
                    "%s failed (attempt %s/%s): %s. Retrying after %.2fs",
                    action_name,
                    attempt,
                    HTTP_MAX_RETRIES,
                    exc,
                    HTTP_RETRY_BACKOFF_SECONDS * attempt,
                )
                time.sleep(HTTP_RETRY_BACKOFF_SECONDS * attempt)
            else:
                logger.error("%s exhausted retries: %s", action_name, exc)
    return None


def notify_pushover(issue_title: str, issue_number: int, message: str):
    """Send push notification via Pushover with contextual GitHub issue link."""
    if not (PUSHOVER_USER_KEY and PUSHOVER_API_TOKEN):
        logger.warning("⚠️ Pushover not configured, skipping notification.")
        return
    issue_url = f"https://github.com/{REPO}/issues/{issue_number}"
    response = _send_with_retries(
        "Pushover notification",
        lambda: requests.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token": PUSHOVER_API_TOKEN,
                "user": PUSHOVER_USER_KEY,
                "title": issue_title,
                "message": message,
                "url": issue_url,
                "url_title": f"View issue #{issue_number}",
            },
            timeout=HTTP_TIMEOUT,
        ),
    )
    if response and response.ok:
        logger.info("📱 Pushover notification sent.")
    elif response is not None:
        logger.error("❌ Pushover notification failed: %s %s", response.status_code, response.text)


def post_github_comment(issue_number: int, issue_title: str, body: str):
    """Post a comment to a GitHub issue."""
    url = f"https://api.github.com/repos/{REPO}/issues/{issue_number}/comments"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    data = {"body": body}

    response = _send_with_retries(
        "GitHub comment",
        lambda: requests.post(url, json=data, headers=headers, timeout=HTTP_TIMEOUT),
    )
    if not response:
        logger.error("❌ Failed to post comment: network error")
        return
    if response.status_code not in [200, 201]:
        logger.error("❌ Failed to post comment: %s %s", response.status_code, response.text)
        return

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
        "- Preserve every requirement, constraint, data detail, and acceptance criterion from the Product Owner message, and list them under a `Preserved Requirements` heading before the final prompt to confirm coverage.\n"
        "- Expand terse descriptions so the resulting prompt is very detailed, leaving no ambiguity for the implementer.\n"
        "- Keep it fully in English.\n"
        "- Focus on what needs to be implemented (new features, changes, endpoints, data model updates).\n"
        "- Avoid repetition or irrelevant context beyond what is necessary to preserve meaning.\n"
        "- Output the preserved requirements list followed by the Codex prompt, ready to be pasted in terminal.\n"
        "\nExample output:\n"
        "Implement a new FastAPI endpoint `POST /decks/import` allowing users to import a deck from Moxfield. "
        "Use the existing `Deck` model in `models/deck.py`. Validate user authentication via `get_current_user()`. "
        "On success, return the new deck as JSON.\n\n"
        "---\n\n"
        "Now rewrite this message from the Product Owner into such a Codex-ready prompt without omitting any detail."
    )

    try:
        if not openai_client:
            raise RuntimeError(f"OpenAI client unavailable: {_OPENAI_IMPORT_ERROR}")

        completion = openai_client.responses.create(
            model=OPENAI_MODEL,
            input=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": issue_text,
                },
            ],
            temperature=0.4,
        )
        return completion.output_text.strip()
    except Exception as e:
        logger.error(f"❌ OpenAI API error: {e}")
        return "⚠️ Failed to generate Codex prompt."


# --------------- WEBHOOK ENDPOINT ---------------


def _verify_signature(header_signature: Optional[str], payload: bytes) -> bool:
    if not header_signature:
        return False
    try:
        algo, signature = header_signature.split("=", 1)
    except ValueError:
        return False
    if algo != "sha256":
        return False
    digest = hmac.new(GITHUB_WEBHOOK_SECRET.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


@app.post("/github-webhook-codex")
async def github_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    if not _verify_signature(signature, raw_body):
        logger.warning("❌ Invalid GitHub signature, rejecting request.")
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.error("❌ Failed to decode JSON payload from GitHub.")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

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
