import base64
import io
import json
import logging
from unittest import mock

import pytest
import requests
from PIL import Image

import gemini_api
from gemini_api import GeminiError, analyze_meal_image, generate_daily_summary, image_to_jpeg_base64
from helpers import FAKE_KEY, MEAL, gemini_body, make_response, meal_response, png_bytes
from nutrition import compute_daily_totals

# Worst case for a leak: an error response whose URL still carries the key.
LEAKY_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={FAKE_KEY}"

INVALID_KEY_BODY = {
    "error": {
        "code": 400,
        "message": "API key not valid. Please pass a valid API key.",
        "status": "INVALID_ARGUMENT",
        "details": [
            {
                "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                "reason": "API_KEY_INVALID",
                "domain": "googleapis.com",
            }
        ],
    }
}
OVERLOADED_BODY = {
    "error": {"code": 503, "message": "The model is overloaded. Please try again later.", "status": "UNAVAILABLE"}
}


@pytest.fixture
def post(monkeypatch):
    fake = mock.Mock(return_value=meal_response())
    monkeypatch.setattr(requests, "post", fake)
    return fake


def test_analyze_meal_image_returns_parsed_meal(post):
    result = analyze_meal_image("aW1hZ2U=")

    assert result == MEAL
    assert isinstance(result["calories"], float)


def test_request_uses_json_response_schema_and_inline_image(post):
    analyze_meal_image("aW1hZ2U=")

    payload = post.call_args.kwargs["json"]
    assert payload["generationConfig"]["responseMimeType"] == "application/json"
    assert payload["generationConfig"]["responseSchema"] == gemini_api.MEAL_SCHEMA
    assert payload["contents"][0]["parts"][1] == {
        "inlineData": {"mimeType": "image/jpeg", "data": "aW1hZ2U="}
    }


def test_api_key_is_sent_in_header_not_url(post):
    analyze_meal_image("aW1hZ2U=")

    url = post.call_args.args[0]
    headers = post.call_args.kwargs["headers"]
    assert headers["x-goog-api-key"] == FAKE_KEY
    assert FAKE_KEY not in url
    assert "key=" not in url
    assert url == "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    assert post.call_args.kwargs["timeout"] == gemini_api.REQUEST_TIMEOUT_SECONDS


def test_model_can_be_overridden_by_env(post, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-pro")
    analyze_meal_image("aW1hZ2U=")

    assert post.call_args.args[0].endswith("/models/gemini-2.5-pro:generateContent")


def test_missing_key_fails_without_a_request(post, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY")

    with pytest.raises(GeminiError, match="GEMINI_API_KEY is not set"):
        analyze_meal_image("aW1hZ2U=")
    post.assert_not_called()


def _assert_key_not_exposed(error, caplog, capsys):
    message = str(error)
    assert FAKE_KEY not in message and "key=" not in message
    assert FAKE_KEY not in repr(error)
    assert error.__cause__ is None and error.__context__ is None
    assert FAKE_KEY not in caplog.text
    captured = capsys.readouterr()
    assert FAKE_KEY not in captured.out and FAKE_KEY not in captured.err


@pytest.mark.parametrize(
    "status, body, expected_calls",
    [(400, INVALID_KEY_BODY, 1), (503, OVERLOADED_BODY, gemini_api.MAX_ATTEMPTS)],
)
def test_http_error_does_not_expose_key(monkeypatch, caplog, capsys, status, body, expected_calls):
    caplog.set_level(logging.DEBUG)
    response = make_response(status, body, LEAKY_URL)
    with pytest.raises(requests.HTTPError, match="key="):
        response.raise_for_status()  # the requests exception text would have leaked the key
    post = mock.Mock(return_value=response)
    monkeypatch.setattr(requests, "post", post)

    with pytest.raises(GeminiError) as excinfo:
        analyze_meal_image("aW1hZ2U=")

    assert f"HTTP {status}" in str(excinfo.value)
    assert post.call_count == expected_calls  # 503 is retried, 400 is not
    _assert_key_not_exposed(excinfo.value, caplog, capsys)


def test_connection_error_does_not_expose_key(monkeypatch, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    error = requests.ConnectionError(f"HTTPSConnectionPool(host='x', port=443): Max retries exceeded with url: {LEAKY_URL}")
    monkeypatch.setattr(requests, "post", mock.Mock(side_effect=error))

    with pytest.raises(GeminiError) as excinfo:
        analyze_meal_image("aW1hZ2U=")

    assert "Could not reach the Gemini API" in str(excinfo.value)
    _assert_key_not_exposed(excinfo.value, caplog, capsys)


def test_daily_summary_error_does_not_expose_key(monkeypatch, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(requests, "post", mock.Mock(return_value=make_response(400, INVALID_KEY_BODY, LEAKY_URL)))

    with pytest.raises(GeminiError) as excinfo:
        generate_daily_summary([MEAL], compute_daily_totals([MEAL]))

    _assert_key_not_exposed(excinfo.value, caplog, capsys)


def test_daily_summary_sends_python_totals_and_returns_text(monkeypatch):
    meals = [MEAL, {**MEAL, "foodName": "Greek yogurt", "calories": 150.5}]
    totals = compute_daily_totals(meals)
    post = mock.Mock(return_value=make_response(200, gemini_body("## Assessment\nLooks balanced."), "https://example.invalid"))
    monkeypatch.setattr(requests, "post", post)

    text = generate_daily_summary(meals, totals)

    assert text == "## Assessment\nLooks balanced."
    prompt = post.call_args.kwargs["json"]["contents"][0]["parts"][0]["text"]
    assert "Totals for the day: 760.5 kcal, protein 57 g, carbs 144 g, fat 42.8 g" in prompt
    assert "do not recalculate" in prompt


def test_blocked_prompt_gives_a_clear_error(monkeypatch):
    body = {"promptFeedback": {"blockReason": "SAFETY"}, "modelVersion": "gemini-2.5-flash"}
    monkeypatch.setattr(requests, "post", mock.Mock(return_value=make_response(200, body, "https://example.invalid")))

    with pytest.raises(GeminiError, match="blocked: SAFETY"):
        analyze_meal_image("aW1hZ2U=")


def _decode(b64: str) -> Image.Image:
    image = Image.open(io.BytesIO(base64.b64decode(b64)))
    image.load()
    return image


def test_jpeg_cannot_store_rgba_directly():
    # The original app called image.save(format="JPEG") on the upload as-is.
    with pytest.raises(OSError):
        Image.new("RGBA", (4, 4)).save(io.BytesIO(), format="JPEG")


@pytest.mark.parametrize("mode", ["RGBA", "P", "LA", "L", "RGB"])
def test_png_uploads_are_converted_to_rgb_jpeg(mode):
    upload = Image.open(io.BytesIO(png_bytes(mode)))
    assert upload.mode == mode

    result = _decode(image_to_jpeg_base64(upload))

    assert result.format == "JPEG"
    assert result.mode == "RGB"
    assert result.size == (64, 48)


def test_transparent_pixels_become_white():
    upload = Image.open(io.BytesIO(png_bytes("RGBA")))  # fully transparent

    pixel = _decode(image_to_jpeg_base64(upload)).getpixel((10, 10))

    assert all(channel >= 250 for channel in pixel)


def test_large_images_are_scaled_down():
    upload = Image.new("RGB", (4000, 3000))

    result = _decode(image_to_jpeg_base64(upload))

    assert max(result.size) == gemini_api.MAX_IMAGE_SIDE
    assert result.size == (1600, 1200)


def test_unexpected_json_shape_is_rejected(monkeypatch):
    monkeypatch.setattr(
        requests, "post", mock.Mock(return_value=make_response(200, gemini_body(json.dumps([1, 2])), "https://x"))
    )
    with pytest.raises(GeminiError, match="unexpected format"):
        analyze_meal_image("aW1hZ2U=")
