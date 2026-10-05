import dotenv
import pytest
import requests

import database
import gemini_api
from helpers import FAKE_KEY


def _no_network(*args, **kwargs):
    raise AssertionError("a test tried to make a real HTTP request")


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch):
    """Fake key, no database, default model, no .env loading, no real HTTP, no retry delay."""
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_KEY)
    monkeypatch.delenv("MONGO_URI", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)
    monkeypatch.setattr(requests, "post", _no_network)
    monkeypatch.setattr(gemini_api, "RETRY_BASE_DELAY_SECONDS", 0)
    monkeypatch.setattr(database, "_client", None)
    monkeypatch.setattr(database, "_warned_missing_uri", False)
