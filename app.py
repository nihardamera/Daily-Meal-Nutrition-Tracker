import streamlit as st
from PIL import Image
import base64
import io
from gemini_api import analyze_meal_image, generate_daily_summary

st.set_page_config(
    page_title="Daily Meal Nutrition Tracker",
    page_icon="🍽️🥣",
    layout="wide"
)

if 'daily_meals' not in st.session_state:
    st.session_state.daily_meals = []

def markdown_to_html(text):
    return text.replace("\n", "<br>").replace("### ", "<h3>").replace("## ", "<h2>").replace("**", "<b>")


st.title("🍽️🥣 Daily Meal Nutrition Tracker")
st.markdown("Upload a photo of your meal to get a detailed nutritional analysis and track your daily intake.")

st.markdown("---")

st.header("Step 1: Upload Your Meal Photo")
uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.image(image, caption='Your Uploaded Meal', use_column_width=True)

    with col2:
        with st.spinner("🤖 Analyzing your meal... This may take a moment."):
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            analysis_data = analyze_meal_image(img_base64)

            if analysis_data and "error" not in analysis_data:
                st.session_state.daily_meals.append(analysis_data)
                
                st.header("Step 2: Nutritional Analysis")
                st.success("Analysis Complete!")
                
                st.subheader(f"Identified Meal: **{analysis_data['foodName']}**")
                st.write(f"Estimated Serving Size: {analysis_data['servingSize']}")
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Calories", f"{analysis_data['calories']} kcal")
                c2.metric("Protein", f"{analysis_data['nutrients']['protein']} g")
                c3.metric("Carbs", f"{analysis_data['nutrients']['carbs']} g")
                c4.metric("Fat", f"{analysis_data['nutrients']['fat']} g")

                with st.expander("Vitamin & Mineral Estimates"):
                    vitamins = analysis_data.get('vitamins', {})
                    vit_c = vitamins.get('vitamin_c', 0)
                    vit_d = vitamins.get('vitamin_d', 0)
                    iron = vitamins.get('iron', 0)
                    
                    st.write(f"**Vitamin C:** {vit_c} mg")
                    st.write(f"**Vitamin D:** {vit_d} mcg")
                    st.write(f"**Iron:** {iron} mg")

            else:
                st.error(f"Could not analyze the image. Please try another one. Error: {analysis_data.get('error', 'Unknown error')}")

st.markdown("---")

st.header("Step 3: Your Daily Summary")

if not st.session_state.daily_meals:
    st.info("You haven't logged any meals yet. Upload a photo to get started!")
else:
    st.subheader("Logged Meals Today:")
    for i, meal in enumerate(st.session_state.daily_meals):
        st.write(f"**{i+1}. {meal['foodName']}**: {meal['calories']} kcal")
    
    if st.button("✨ Generate Daily Report", use_container_width=True):
        with st.spinner("✍️ Generating your daily report..."):
            summary_text = generate_daily_summary(st.session_state.daily_meals)
            if "Error" in summary_text:
                st.error(summary_text)
            else:
                st.subheader("Your Daily Nutritional Report")
                st.markdown(summary_text, unsafe_allow_html=True)
