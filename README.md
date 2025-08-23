# Agentic AI Nutrition Tracker

This is a Python application that uses AI to analyze meals from images, track nutritional intake, and provide a daily summary with dietary suggestions.

## Features

  - **Image-to-Nutrition Analysis**: Upload a photo of your meal to get an instant breakdown of the food item, serving size, calories, and macronutrients.
  - **Daily Meal Logging**: Automatically logs each analyzed meal to track your daily consumption.
  - **AI-Powered Daily Summary**: Generates a comprehensive report of your total intake at the end of the day.
  - **Personalized Suggestions**: Provides recommendations on what to eat to balance your diet based on your daily intake.

## Tech Stack

  - **Frontend**: Streamlit
  - **AI/ML**: Google Gemini API
  - **Language**: Python

## Setup and Installation

1.  **Clone the Repository**

    ```bash
    git clone [https://github.com/YOUR_USERNAME/agentic-nutrition-app.git](https://github.com/YOUR_USERNAME/agentic-nutrition-app.git)
    cd agentic-nutrition-app
    ```

2.  **Create a Virtual Environment**

    It's recommended to use a virtual environment to manage project dependencies.

    ```bash
    # For macOS/Linux
    python3 -m venv venv
    source venv/bin/activate

    # For Windows
    python -m venv venv
    .\venv\Scripts\activate
    ```

3.  **Install Dependencies**

    Install all the required libraries using the `requirements.txt` file.

    ```bash
    pip install -r requirements.txt
    ```

4.  **Set Up Your API Key**

    This project requires a Google Gemini API key.

      - Obtain your API key from the [Google AI Studio](https://aistudio.google.com/app/apikey).
      - Create a `.env` file in the root of the project and add your key:
        ```
        GEMINI_API_KEY="YOUR_API_KEY_HERE"
        ```
      - Ensure you have a `.gitignore` file that includes `.env` to protect your key.

## How to Run the Application

Once you have completed the setup, you can run the Streamlit application with the following command:

```bash 
streamlit run app.py