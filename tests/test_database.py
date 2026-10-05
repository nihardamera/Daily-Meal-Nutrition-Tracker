import logging
from datetime import timezone
from unittest import mock

import pymongo.errors

import database
from helpers import MEAL

FAKE_URI = "mongodb+srv://user:secret-password@cluster0.example.mongodb.net/"


def test_without_mongo_uri_nothing_is_stored(monkeypatch, caplog):
    client_cls = mock.Mock()
    monkeypatch.setattr(database, "MongoClient", client_cls)

    with caplog.at_level(logging.WARNING):
        assert database.log_meal_to_db(MEAL) == "disabled"
        assert database.log_meal_to_db(MEAL) == "disabled"

    client_cls.assert_not_called()
    assert caplog.text.count("MONGO_URI is not set") == 1


def test_document_gets_utc_timestamp_and_meal_is_not_mutated(monkeypatch):
    monkeypatch.setenv("MONGO_URI", FAKE_URI)
    client_cls = mock.MagicMock()
    monkeypatch.setattr(database, "MongoClient", client_cls)
    meal = dict(MEAL)

    assert database.log_meal_to_db(meal) == "saved"

    collection = client_cls.return_value["nutrition_tracker"]["meals"]
    (document,), _ = collection.insert_one.call_args
    assert document["foodName"] == "Chicken biryani"
    assert document["logged_at"].tzinfo is timezone.utc
    assert meal == MEAL  # the session's copy has no _id or timestamp added


def test_client_is_reused(monkeypatch):
    monkeypatch.setenv("MONGO_URI", FAKE_URI)
    client_cls = mock.MagicMock()
    monkeypatch.setattr(database, "MongoClient", client_cls)

    database.log_meal_to_db(MEAL)
    database.log_meal_to_db(MEAL)

    assert client_cls.call_count == 1


def test_insert_failure_is_reported_without_the_uri(monkeypatch, caplog):
    monkeypatch.setenv("MONGO_URI", FAKE_URI)
    client_cls = mock.MagicMock()
    client_cls.return_value.__getitem__.return_value.__getitem__.return_value.insert_one.side_effect = (
        pymongo.errors.ServerSelectionTimeoutError(f"could not connect to {FAKE_URI}")
    )
    monkeypatch.setattr(database, "MongoClient", client_cls)

    with caplog.at_level(logging.WARNING):
        assert database.log_meal_to_db(MEAL) == "failed"

    assert "ServerSelectionTimeoutError" in caplog.text
    assert "secret-password" not in caplog.text
