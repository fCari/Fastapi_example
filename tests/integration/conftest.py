import os
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from app.config import CACHE_KEY


@pytest.fixture
def client():
    # Evitar borrar datos del laboratorio: solo permitir servicios de prueba.
    assert urlparse(os.environ["DATABASE_URL"]).path == "/users_test"
    assert urlparse(os.environ["REDIS_URL"]).path == "/15"

    from app import database, service
    from app.main import app

    with TestClient(app) as test_client:
        with database.connect() as conn:
            conn.execute("TRUNCATE TABLE users RESTART IDENTITY")
        service.cache.delete(CACHE_KEY)
        try:
            yield test_client
        finally:
            with database.connect() as conn:
                conn.execute("TRUNCATE TABLE users RESTART IDENTITY")
            service.cache.delete(CACHE_KEY)
