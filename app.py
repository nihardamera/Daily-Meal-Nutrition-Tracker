import io
import logging
import os

import streamlit as st
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

from database import is_db_configured, log_meal_to_db  # noqa: E402
from gemini_api import (  # noqa: E402
    GeminiError,
    analyze_meal_image,
    generate_daily_summary,
    image_to_jpeg_base64,
)
from nutrition import NUTRIENTS, compute_daily_totals  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

st.set_page_config(page_title="Daily Meal Nutrition Tracker", page_icon="🍽️", layout="wide")

state = st.session_state
state.setdefault("daily_meals", [])
# Upload file_id -> {"meal": dict, "db_status": str} or {"error": str}.
# Streamlit reruns the whole script on every interaction (for example the report button)
# while the upload is still set, so each upload is analysed and logged only the first time.
state.setdefault("analysed_uploads", {})
# (number of meals the report covers, report markdown)
state.setdefault("daily_report", None)

UNREADABLE_IMAGE = "This file could not be read as an image."


def format_amount(key: str, value: float) -> str:
    return f"{value:,.0f}" if key == "calories" else f"{value:,.1f}"


def analyse_upload(uploaded_file) -> dict:
    upload_id = uploaded_file.file_id
    if upload_id in state.analysed_uploads:
        return state.analysed_uploads[upload_id]

    try:
        image_b64 = image_to_jpeg_base64(Image.open(io.BytesIO(uploaded_file.getvalue())))
    except OSError:
        result = {"error": UNREADABLE_IMAGE}
    else:
        try:
            with st.spinner("Analysing your meal..."):
                meal = analyze_meal_image(image_b64)
        except GeminiError as exc:
            result = {"error": f"{exc} Remove the photo and upload it again to retry."}
        else:
            state.daily_meals.append(meal)
            result = {"meal": meal, "db_status": log_meal_to_db(meal)}

    state.analysed_uploads[upload_id] = result
    return result


def show_meal(result: dict) -> None:
    if "error" in result:
        st.error(f"Could not analyse this image. {result['error']}")
        return

    meal = result["meal"]
    st.subheader(meal["foodName"])
    st.write(f"Estimated serving size: {meal['servingSize']}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Calories", f"{format_amount('calories', meal['calories'])} kcal")
    c2.metric("Protein", f"{format_amount('protein', meal['nutrients']['protein'])} g")
    c3.metric("Carbs", f"{format_amount('carbs', meal['nutrients']['carbs'])} g")
    c4.metric("Fat", f"{format_amount('fat', meal['nutrients']['fat'])} g")
    with st.expander("Vitamin and mineral estimates"):
        vitamins = meal["vitamins"]
        st.write(f"Vitamin C: {vitamins['vitamin_c']:g} mg")
        st.write(f"Vitamin D: {vitamins['vitamin_d']:g} mcg")
        st.write(f"Iron: {vitamins['iron']:g} mg")
    if result["db_status"] == "failed":
        st.warning("The meal is in today's log, but it could not be saved to the database.")


st.title("Daily Meal Nutrition Tracker")
st.markdown(
    "Upload a photo of a meal to get an estimate of its calories and nutrients, "
    "then generate a summary of everything logged in this session. "
    "All values are estimates from a photo, not medical or dietary advice."
)
if not os.environ.get("GEMINI_API_KEY"):
    st.warning("GEMINI_API_KEY is not set, so meals cannot be analysed. See the README for setup.")
if not is_db_configured():
    st.caption("MONGO_URI is not set: meals are kept in this browser session only.")

st.divider()
st.header("1. Upload a meal photo")
uploaded_file = st.file_uploader("Choose an image", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    col_image, col_result = st.columns(2)
    with col_result:
        result = analyse_upload(uploaded_file)
        show_meal(result)
    with col_image:
        if result.get("error") != UNREADABLE_IMAGE:
            st.image(uploaded_file.getvalue(), caption="Your meal", width="stretch")

st.divider()
st.header("2. Today's log")

meals = state.daily_meals
if not meals:
    st.info("No meals logged yet. Upload a photo to start.")
else:
    for i, meal in enumerate(meals, start=1):
        st.write(f"{i}. **{meal['foodName']}**: {format_amount('calories', meal['calories'])} kcal")

    totals = compute_daily_totals(meals)
    st.subheader("Totals")
    for column, (key, label, unit, _) in zip(st.columns(len(NUTRIENTS)), NUTRIENTS):
        column.metric(label, f"{format_amount(key, totals[key])} {unit}")

    if st.button("Generate daily report", width="stretch"):
        with st.spinner("Writing your daily report..."):
            try:
                state.daily_report = (len(meals), generate_daily_summary(meals, totals))
            except GeminiError as exc:
                state.daily_report = None
                st.error(f"Could not generate the report. {exc}")

    if state.daily_report and state.daily_report[0] == len(meals):
        st.subheader("Daily report")
        st.markdown(state.daily_report[1])
