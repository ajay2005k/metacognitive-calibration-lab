import os
from pymongo import ASCENDING, MongoClient


def connect():
    client = MongoClient(
        os.getenv("MONGO_URI", "mongodb://localhost:27017/mclab"),
        serverSelectionTimeoutMS=3000,
    )
    return client.get_default_database(default="mclab")


def create_indexes(db):
    db.participants.create_index("participant_id", unique=True)
    db.sessions.create_index("session_id", unique=True)
    db.sessions.create_index("participant_id")
    db.trials.create_index(
        [("session_id", ASCENDING), ("item_id", ASCENDING)], unique=True
    )
    db.trials.create_index(
        [("session_id", ASCENDING), ("trial_no", ASCENDING)], unique=True
    )
    db.reports.create_index("session_id", unique=True)
