"""Optional MongoDB log of analysed meals.

If MONGO_URI is not set, nothing is stored and the app still runs.
The app only writes to this collection; it never reads meals back.
"""

import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi

load_dotenv()

logger = logging.getLogger(__name__)

DB_NAME = "nutrition_tracker"
COLLECTION_NAME = "meals"

_client = None
_warned_missing_uri = False


def is_db_configured() -> bool:
    return bool(os.environ.get("MONGO_URI"))


def _get_collection():
    global _client
    if _client is None:
        _client = MongoClient(
            os.environ["MONGO_URI"], server_api=ServerApi("1"), serverSelectionTimeoutMS=5000
        )
    return _client[DB_NAME][COLLECTION_NAME]


def log_meal_to_db(meal_data: dict) -> str:
    """Insert a copy of the meal with a UTC `logged_at` timestamp.

    Returns "saved", "disabled" (MONGO_URI not set) or "failed".
    Failures are logged by exception type only, so the connection string never reaches the logs.
    """
    global _warned_missing_uri
    if not is_db_configured():
        if not _warned_missing_uri:
            logger.warning("MONGO_URI is not set; meals will not be saved to a database.")
            _warned_missing_uri = True
        return "disabled"

    document = {**meal_data, "logged_at": datetime.now(timezone.utc)}
    try:
        result = _get_collection().insert_one(document)
    except Exception as exc:  # pymongo raises many error types; none should stop the app
        logger.warning("Could not save meal to MongoDB: %s", type(exc).__name__)
        return "failed"
    logger.info("Saved meal to MongoDB with id %s", result.inserted_id)
    return "saved"
