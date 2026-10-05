# Daily Meal Nutrition Tracker

A Streamlit app that estimates the calories and nutrients of a meal from a photo using the Google Gemini API, and keeps a running log of the meals analysed in the current session.

## What it does

- You upload a photo of a meal (JPG or PNG). The app sends it to Gemini and shows the estimated dish name, serving size, calories, protein, carbohydrates, fat, vitamin C, vitamin D and iron.
- Each analysed meal is added to a log for the current browser session. Each upload is analysed once; clicking buttons or other reruns of the page do not send it again.
- The app adds up the totals for the log itself, in Python, from the per-meal estimates.
- "Generate daily report" sends the logged meals and those totals to Gemini, which writes a short assessment against general daily reference intakes and suggests foods for nutrients that look low. The prompt tells the model to use the totals as given rather than recalculate them.
- If `MONGO_URI` is set, each analysed meal is also inserted into MongoDB (database `nutrition_tracker`, collection `meals`) with a UTC `logged_at` timestamp.

## How the Gemini calls work

`gemini_api.py` calls the Gemini REST endpoint `generateContent` with `requests`; it does not use an SDK.

For the meal analysis, the request sets `responseMimeType` to `application/json` and passes a `responseSchema` (`MEAL_SCHEMA`) that requires these fields:

| Field | Type | Unit |
| --- | --- | --- |
| `foodName` | string | |
| `servingSize` | string | free text, for example "1 plate (about 350 g)" |
| `calories` | number | kcal |
| `nutrients.protein`, `nutrients.carbs`, `nutrients.fat` | number | g |
| `vitamins.vitamin_c` | number | mg |
| `vitamins.vitamin_d` | number | mcg |
| `vitamins.iron` | number | mg |

Gemini's answer is therefore a JSON object with these keys. The app parses it with `json.loads`, rejects anything that is not an object with a `foodName`, and treats a missing or non-numeric value as 0.

Other details:

- Before sending, the photo is converted to an RGB JPEG (transparent areas become white) and scaled down so its longer side is at most 1600 px.
- The API key is sent in the `x-goog-api-key` header, not in the URL. Errors shown in the app or written to the log give the HTTP status, never the request URL, the key or the raw `requests` exception text.
- Network errors and HTTP 429 or 5xx responses are retried, up to 3 attempts in total. Other errors (for example an invalid key) fail immediately.
- The daily report is a plain text request without a schema. The model's markdown is shown as is.

## Project layout

| Path | Contents |
| --- | --- |
| `app.py` | Streamlit page and session state |
| `gemini_api.py` | Gemini requests, image preparation, response parsing |
| `nutrition.py` | Daily totals |
| `database.py` | Optional MongoDB logging |
| `tests/` | pytest tests; Gemini and MongoDB are mocked, so they need no key or network |

## Setup

You need Python 3.10 or newer (tested with 3.12) and a Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey). MongoDB is optional.

```bash
git clone https://github.com/nihardamera/Daily-Meal-Nutrition-Tracker.git
cd Daily-Meal-Nutrition-Tracker
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Or with [uv](https://docs.astral.sh/uv/): `uv venv` then `uv pip install -r requirements.txt`.

Create a `.env` file in the project folder (it is in `.gitignore`) or set the variables in your shell. Variables already set in the environment take precedence over `.env`.

```
GEMINI_API_KEY=your-gemini-api-key
MONGO_URI=mongodb+srv://user:password@cluster.example.mongodb.net/
GEMINI_MODEL=gemini-2.5-flash
```

| Variable | Required | Purpose |
| --- | --- | --- |
| `GEMINI_API_KEY` | yes | Gemini API key. Without it the page loads but cannot analyse photos. |
| `MONGO_URI` | no | MongoDB connection string. If unset, meals are not saved anywhere; the app shows a note and logs a warning. |
| `GEMINI_MODEL` | no | Gemini model id. Defaults to `gemini-2.5-flash`. |

## Run

```bash
streamlit run app.py
```

Streamlit prints the local URL, normally http://localhost:8501.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The tests replace `requests.post` with a mock that returns responses shaped like Gemini `generateContent` responses. They check the parsed meal, that the key is sent in the header and not the URL, that HTTP and network errors do not expose the key, conversion of RGBA and palette PNGs, the Python-side totals, that MongoDB is optional, and (using Streamlit's `AppTest`) that clicking "Generate daily report" does not analyse or log the same upload a second time.

## Limitations

- All values are rough estimates from a single photo; portion size in particular is hard to judge from an image. This is not medical or dietary advice.
- Each photo becomes one log entry. A photo of several dishes gives one combined estimate.
- The daily log lives in the Streamlit session. Refreshing the page or restarting the app clears it, and "today" means "this session", not a calendar day.
- The MongoDB collection is a write-only log. The app inserts meals but never reads them back, so earlier sessions are not shown.
- Every photo analysis and every report is one Gemini API request and counts against your API quota.
