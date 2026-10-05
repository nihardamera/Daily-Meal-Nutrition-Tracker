import io
import json

import requests
from PIL import Image

FAKE_KEY = "test-key-not-real-123"

# A meal as the model returns it under MEAL_SCHEMA.
MEAL = {
    "foodName": "Chicken biryani",
    "servingSize": "1 plate (about 350 g)",
    "calories": 610,
    "nutrients": {"protein": 28.5, "carbs": 72, "fat": 21.4},
    "vitamins": {"vitamin_c": 6.2, "vitamin_d": 0.3, "iron": 2.8},
}


def gemini_body(text: str) -> dict:
    """Shape of a successful generateContent response (v1beta REST)."""
    return {
        "candidates": [
            {
                "content": {"parts": [{"text": text}], "role": "model"},
                "finishReason": "STOP",
                "index": 0,
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 1342,
            "candidatesTokenCount": 118,
            "totalTokenCount": 1716,
            "promptTokensDetails": [
                {"modality": "TEXT", "tokenCount": 84},
                {"modality": "IMAGE", "tokenCount": 1258},
            ],
            "thoughtsTokenCount": 256,
        },
        "modelVersion": "gemini-2.5-flash",
        "responseId": "kD3iaN2xLYyQ1MkPn8eW-Ag",
    }


def make_response(status: int, body: dict, url: str) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(body).encode()
    response.headers["Content-Type"] = "application/json; charset=UTF-8"
    response.url = url
    response.reason = {200: "OK", 400: "Bad Request", 503: "Service Unavailable"}.get(status, "")
    return response


def meal_response(meal: dict = MEAL) -> requests.Response:
    # JSON mode returns the object as pretty-printed text inside parts[0].text.
    return make_response(200, gemini_body(json.dumps(meal, indent=2)), "https://example.invalid")


def png_bytes(mode: str = "RGBA", size=(64, 48)) -> bytes:
    if mode == "P":
        image = Image.new("P", size, 0)
        image.putpalette([255, 0, 0, 0, 128, 0] + [0] * 762)
        image.info["transparency"] = 0
    else:
        color = {"RGBA": (200, 120, 40, 0), "LA": (90, 0), "L": 90, "RGB": (200, 120, 40)}[mode]
        image = Image.new(mode, size, color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
