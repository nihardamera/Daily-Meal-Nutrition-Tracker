load_dotenv()

mongo_uri = os.environ.get("MONGO_URI")

def get_db_client():
    return MongoClient(mongo_uri, server_api=ServerApi('1'))

def log_meal_to_db(meal_data: dict):
    client = None
    try:
        client = get_db_client()
        # Ping the database to confirm a successful connection
        client.admin.command('ping')
        print("Successfully connected to MongoDB!")

        # Select your database and collection
        db = client.nutrition_tracker 
        collection = db.meals

        # Insert the meal_data dictionary directly into the collection
        result = collection.insert_one(meal_data)
        
        if result.inserted_id:
            print(f"Successfully logged meal to database with ID: {result.inserted_id}")
            return "Success"
        else:
            print("Error logging meal: No document was inserted.")
            return "Error: No document was inserted."
            
    except Exception as e:
        print(f"An exception occurred: {e}")
        return f"An exception occurred: {e}"
    finally:
        # Ensure the client connection is closed to prevent leaks
        if client:
            client.close()