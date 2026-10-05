"""Calls to the Gemini REST API (generateContent) for meal analysis and the daily summary."""

import base64
import io
import json
import logging
import os
import time

import requests
from dotenv import load_dotenv
from PIL import Image, ImageOps

from nutrition import to_number

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.5-flash"
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
REQUEST_TIMEOUT_SECONDS = 60
MAX_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 1
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_IMAGE_SIDE = 1600

MEAL_PROMPT = """
Analyze the food in this image.
1. Identify the food item or dish.
2. Estimate the serving size shown (for example in grams or cups).
3. Estimate the total calories for that serving.
4. Estimate protein (g), carbohydrates (g) and fat (g).
5. Estimate vitamin C (mg), vitamin D (mcg) and iron (mg).
All numbers are for the whole serving shown.
"""

MEAL_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "foodName": {"type": "STRING"},
        "servingSize": {"type": "STRING"},
        "calories": {"type": "NUMBER"},
        "nutrients": {
            "type": "OBJECT",
            "properties": {
                "protein": {"type": "NUMBER"},
                "carbs": {"type": "NUMBER"},
                "fat": {"type": "NUMBER"},
            },
            "required": ["protein", "carbs", "fat"],
        },
        "vitamins": {
            "type": "OBJECT",
            "properties": {
                "vitamin_c": {"type": "NUMBER"},
                "vitamin_d": {"type": "NUMBER"},
                "iron": {"type": "NUMBER"},
            },
            "required": ["vitamin_c", "vitamin_d", "iron"],
        },
    },
    "required": ["foodName", "servingSize", "calories", "nutrients", "vitamins"],
}


class GeminiError(Exception):
    """A Gemini call failed.

    The message is safe to show to users: it never contains the API key,
    the request URL or the text of the underlying requests exception.
    """


def get_model() -> str:
    return os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL


def _endpoint() -> str:
    return f"{API_BASE}/{get_model()}:generateContent"


def _http_error_message(response) -> str:
    """Build a user-safe message from an error response: status code and API status only."""
    status = ""
    try:
        status = response.json().get("error", {}).get("status", "")
    except (ValueError, AttributeError):
        pass
    message = f"Gemini API request failed (HTTP {response.status_code}{', ' + status if status else ''})."
    if response.status_code in (400, 401, 403):
        message += " Check that GEMINI_API_KEY is set to a valid key."
    elif response.status_code == 404:
        message += f" Check that the model '{get_model()}' exists (set GEMINI_MODEL to override)."
    elif response.status_code == 429:
        message += " The quota or rate limit was exceeded; try again later."
    return message


def call_gemini_api(payload: dict) -> str:
    """POST a generateContent request and return the text of the first candidate.

    The key is sent in the x-goog-api-key header, never in the URL.
    Raises GeminiError with a user-safe message on any failure.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise GeminiError("GEMINI_API_KEY is not set. Add it to your environment or .env file.")

    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    delay = RETRY_BASE_DELAY_SECONDS
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.post(
                _endpoint(), json=payload, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS
            )
        except requests.exceptions.RequestException as exc:
            # Log the exception type only: its text can include request details.
            logger.warning(
                "Gemini request attempt %d/%d failed: %s", attempt, MAX_ATTEMPTS, type(exc).__name__
            )
            message = "Could not reach the Gemini API. Check your network connection and try again."
            retry = True
        else:
            if response.ok:
                return _extract_text(response)
            message = _http_error_message(response)
            logger.warning("Gemini request attempt %d/%d failed: %s", attempt, MAX_ATTEMPTS, message)
            retry = response.status_code in RETRYABLE_STATUS_CODES

        if not retry or attempt == MAX_ATTEMPTS:
            raise GeminiError(message)
        time.sleep(delay)
        delay *= 2

    raise GeminiError("Gemini API request failed.")  # not reached


def _extract_text(response) -> str:
    try:
        result = response.json()
    except ValueError:
        raise GeminiError("Gemini returned a response that is not JSON.") from None

    candidates = result.get("candidates") or []
    if not candidates:
        reason = result.get("promptFeedback", {}).get("blockReason")
        raise GeminiError(f"Gemini returned no answer{f' (blocked: {reason})' if reason else ''}.")

    candidate = candidates[0]
    parts = candidate.get("content", {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts if not part.get("thought"))
    if not text:
        reason = candidate.get("finishReason", "unknown")
        raise GeminiError(f"Gemini returned an empty answer (finish reason: {reason}).")
    return text


def image_to_jpeg_base64(image: Image.Image) -> str:
    """Return the image as base64-encoded JPEG.

    Applies the EXIF rotation, converts modes JPEG cannot store (RGBA, P, LA, ...)
    to RGB with transparent areas filled white, and scales the longest side down
    to MAX_IMAGE_SIDE pixels.
    """
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        image = Image.new("RGB", rgba.size, (255, 255, 255))
        image.paste(rgba, mask=rgba.getchannel("A"))
    elif image.mode != "RGB":
        image = image.convert("RGB")
    image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _normalise_meal(raw) -> dict:
    if not isinstance(raw, dict) or not raw.get("foodName"):
        raise GeminiError("Gemini returned an analysis in an unexpected format.")
    nutrients = raw.get("nutrients") or {}
    vitamins = raw.get("vitamins") or {}
    return {
        "foodName": str(raw["foodName"]),
        "servingSize": str(raw.get("servingSize", "")),
        "calories": to_number(raw.get("calories")),
        "nutrients": {key: to_number(nutrients.get(key)) for key in ("protein", "carbs", "fat")},
        "vitamins": {key: to_number(vitamins.get(key)) for key in ("vitamin_c", "vitamin_d", "iron")},
    }


def analyze_meal_image(base64_image_data: str) -> dict:
    """Ask Gemini for a nutrition estimate of a JPEG image.

    The request sets responseMimeType to application/json with MEAL_SCHEMA as the
    response schema, so the answer is a JSON object with fixed keys.
    """
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": MEAL_PROMPT},
                    {"inlineData": {"mimeType": "image/jpeg", "data": base64_image_data}},
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": MEAL_SCHEMA,
        },
    }
    text = call_gemini_api(payload)
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        raise GeminiError("Gemini returned an analysis that is not valid JSON.") from None
    return _normalise_meal(raw)


def generate_daily_summary(daily_meals: list, totals: dict) -> str:
    """Ask Gemini for a written assessment of the day.

    The totals are computed in Python (nutrition.compute_daily_totals) and passed in;
    the model is told to use them as given and only write the assessment and suggestions.
    """
    if not daily_meals:
        raise ValueError("No meals to summarise.")

    meal_lines = []
    for meal in daily_meals:
        nutrients = meal.get("nutrients", {})
        vitamins = meal.get("vitamins", {})
        meal_lines.append(
            f"- {meal.get('foodName', 'Unknown')} ({meal.get('servingSize', 'serving size unknown')}): "
            f"{meal.get('calories', 0):g} kcal, protein {nutrients.get('protein', 0):g} g, "
            f"carbs {nutrients.get('carbs', 0):g} g, fat {nutrients.get('fat', 0):g} g, "
            f"vitamin C {vitamins.get('vitamin_c', 0):g} mg, vitamin D {vitamins.get('vitamin_d', 0):g} mcg, "
            f"iron {vitamins.get('iron', 0):g} mg"
        )

    totals_line = (
        f"{totals['calories']:g} kcal, protein {totals['protein']:g} g, carbs {totals['carbs']:g} g, "
        f"fat {totals['fat']:g} g, vitamin C {totals['vitamin_c']:g} mg, "
        f"vitamin D {totals['vitamin_d']:g} mcg, iron {totals['iron']:g} mg"
    )

    prompt = f"""
The meals below were logged today. Each meal's values are image-based estimates.
The day's totals have already been calculated. Use them exactly as given; do not recalculate them.

Meals:
{chr(10).join(meal_lines)}

Totals for the day: {totals_line}

Write:
1. A short assessment of these totals against general adult daily reference intakes.
2. Suggestions for foods to add if any of these nutrients look low, with one line on why each matters.

Do not repeat the totals as a table. Use markdown headings and bullet lists, and keep it under 250 words.
"""
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    return call_gemini_api(payload)
