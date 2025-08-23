import os
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("GEMINI_API_KEY", "") 
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={API_KEY}"

def call_gemini_api(payload):
    max_retries = 5
    delay = 1  

    for attempt in range(max_retries):
        try:
            response = requests.post(API_URL, json=payload, headers={'Content-Type': 'application/json'})
            response.raise_for_status()
            
            result = response.json()
            if "candidates" in result and result["candidates"][0].get("content", {}).get("parts"):
                return result["candidates"][0]["content"]["parts"][0]["text"]
            else:
                return {"error": "Invalid API response structure", "details": result}

        except requests.exceptions.RequestException as e:
            print(f"API request failed on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                return {"error": "API request failed after multiple retries.", "details": str(e)}
    return {"error": "Failed to get a response from the API."}


def analyze_meal_image(base64_image_data):
    prompt = """
        Analyze the food item in this image. 
        1. Identify the food item precisely.
        2. Estimate the serving size (e.g., in grams or cups) based on the image approximately and accurately.
        3. Based on the food and serving size, estimate the total calories.
        4. Provide a breakdown of key nutrients: Protein (g), Carbohydrates (g), and Fat (g).
        5. Provide a breakdown of key vitamins and minerals: Vitamin C (mg), Vitamin D (mcg), and Iron (mg).

        Return the response as a JSON object with the following keys: 
        "foodName", "servingSize", "calories", 
        "nutrients" (an object with "protein", "carbs", "fat"),
        and "vitamins" (an object with "vitamin_c", "vitamin_d", "iron").
    """
    
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inlineData": {"mimeType": "image/jpeg", "data": base64_image_data}}
            ]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
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
                            "fat": {"type": "NUMBER"}
                        }
                    },
                    "vitamins": {
                        "type": "OBJECT",
                        "properties": {
                            "vitamin_c": {"type": "NUMBER"},
                            "vitamin_d": {"type": "NUMBER"},
                            "iron": {"type": "NUMBER"}
                        }
                    }
                }
            }
        }
    }
    
    response_text = call_gemini_api(payload)
    try:
        if isinstance(response_text, dict):
            return response_text
        return json.loads(response_text)
    except json.JSONDecodeError:
        return {"error": "Failed to decode the API's JSON response.", "details": response_text}


def generate_daily_summary(daily_meals):
    if not daily_meals:
        return "No meals to summarize."

    meals_text = ""
    for meal in daily_meals:
        nutrients = meal.get('nutrients', {})
        vitamins = meal.get('vitamins', {})
        meals_text += (
            f"- {meal.get('foodName', 'N/A')}: "
            f"{meal.get('calories', 0)} kcal, "
            f"{nutrients.get('protein', 0)}g protein, "
            f"{nutrients.get('carbs', 0)}g carbs, "
            f"{nutrients.get('fat', 0)}g fat, "
            f"{vitamins.get('vitamin_c', 0)}mg Vit C, "
            f"{vitamins.get('vitamin_d', 0)}mcg Vit D, "
            f"{vitamins.get('iron', 0)}mg Iron\n"
        )


    prompt = f"""
        Based on the following list of meals consumed today, provide a nutritional summary.
        
        Meals Consumed:
        {meals_text}

        Your summary should include:
        1. Total calorie intake.
        2. Total protein, carbohydrates, and fat intake in grams.
        3. Total intake of Vitamin C, Vitamin D, and Iron.
        4. A brief analysis comparing the total intake to general daily recommendations.
        5. Suggestions for what to include in the diet if any key nutrients, vitamins, or minerals seem low. Briefly mention the importance of each.
        
        Format the response as clean, readable text. Use markdown for headings and lists.
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    summary = call_gemini_api(payload)
    if isinstance(summary, dict) and "error" in summary:
        return f"Error generating summary: {summary['details']}"
    return summary