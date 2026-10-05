"""Runs app.py with Streamlit's AppTest, with requests.post mocked."""

from pathlib import Path
from unittest import mock

import pytest
import requests
from streamlit.testing.v1 import AppTest

from helpers import FAKE_KEY, MEAL, gemini_body, make_response, meal_response, png_bytes

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _report_response():
    return make_response(200, gemini_body("## Assessment\nProtein is on track."), "https://example.invalid")


def _gemini_calls(post):
    """Split recorded calls into meal analyses (image requests) and summaries."""
    images = [c for c in post.call_args_list if "generationConfig" in c.kwargs["json"]]
    return len(images), len(post.call_args_list) - len(images)


@pytest.fixture
def post(monkeypatch):
    fake = mock.Mock(side_effect=lambda *a, **k: _report_response() if "generationConfig" not in k["json"] else meal_response())
    monkeypatch.setattr(requests, "post", fake)
    return fake


@pytest.fixture
def app():
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    assert not at.exception
    return at


def test_app_starts_without_database_or_meals(app):
    assert app.title[0].value == "Daily Meal Nutrition Tracker"
    assert any("MONGO_URI is not set" in c.value for c in app.caption)
    assert app.info[0].value.startswith("No meals logged yet")


def test_rgba_png_upload_is_analysed_once_across_reruns(app, post):
    app.file_uploader[0].upload("lunch.png", png_bytes("RGBA"), "image/png").run()
    assert not app.exception
    assert _gemini_calls(post) == (1, 0)
    assert app.session_state["daily_meals"] == [MEAL]
    assert app.subheader[0].value == "Chicken biryani"

    # Clicking the report button reruns the script with the upload still set.
    app.button[0].click().run()
    assert not app.exception
    assert _gemini_calls(post) == (1, 1)
    assert len(app.session_state["daily_meals"]) == 1
    assert any("Protein is on track." in m.value for m in app.markdown)

    app.run()  # any other rerun
    assert _gemini_calls(post) == (1, 1)
    assert len(app.session_state["daily_meals"]) == 1


def test_totals_shown_are_computed_in_python(app, post):
    app.file_uploader[0].upload("a.png", png_bytes("RGB"), "image/png").run()
    app.file_uploader[0].upload("b.png", png_bytes("RGB"), "image/png").run()

    assert _gemini_calls(post) == (2, 0)
    assert len(app.session_state["daily_meals"]) == 2
    metrics = {m.label: m.value for m in app.metric}
    assert metrics["Calories"] == "1,220 kcal"
    assert metrics["Protein"] == "57.0 g"
    assert metrics["Iron"] == "5.6 mg"


def test_api_error_in_ui_does_not_show_key(app, monkeypatch):
    leaky_url = f"https://generativelanguage.googleapis.com/v1beta/models/x:generateContent?key={FAKE_KEY}"
    body = {"error": {"code": 403, "message": "Permission denied.", "status": "PERMISSION_DENIED"}}
    monkeypatch.setattr(requests, "post", mock.Mock(return_value=make_response(403, body, leaky_url)))

    app.file_uploader[0].upload("dinner.jpg", png_bytes("RGB"), "image/jpeg").run()

    assert not app.exception
    errors = [e.value for e in app.error]
    assert errors and "HTTP 403" in errors[0]
    page_text = " ".join(str(el.value) for el in [*app.error, *app.markdown, *app.warning] if hasattr(el, "value"))
    assert FAKE_KEY not in page_text
    assert app.session_state["daily_meals"] == []


def test_non_image_upload_shows_error(app, post):
    app.file_uploader[0].upload("notes.png", b"not an image", "image/png").run()

    assert not app.exception
    assert "could not be read as an image" in app.error[0].value
    post.assert_not_called()
