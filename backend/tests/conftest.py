import sys
from pathlib import Path
import mongomock
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app import create_app


@pytest.fixture
def app():
    app = create_app(mongomock.MongoClient().mclab)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()
