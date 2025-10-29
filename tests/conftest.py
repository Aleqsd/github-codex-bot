import os
import sys
from pathlib import Path

os.environ.setdefault("GITHUB_TOKEN", "ghp_test_token")
os.environ.setdefault("OPENAI_API_KEY", "sk_test_key")
os.environ.setdefault("WATCH_USER", "GROBimbo")
os.environ.setdefault("REPO", "Aleqsd/EDH-PodLog")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "super-secret")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
