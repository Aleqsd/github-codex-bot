import bot
import pytest


def test_require_env_returns_value(monkeypatch):
    monkeypatch.setenv("SAMPLE_ENV", "value")
    assert bot._require_env("SAMPLE_ENV") == "value"


def test_require_env_raises_for_missing_value(monkeypatch):
    monkeypatch.delenv("MISSING_ENV", raising=False)
    with pytest.raises(RuntimeError, match="MISSING_ENV"):
        bot._require_env("MISSING_ENV")
