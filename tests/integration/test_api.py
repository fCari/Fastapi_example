from app.config import CACHE_KEY, CACHE_TTL


def test_postgres_and_redis_flow(client):
    from app import service

    # Primera consulta: PostgreSQL. Segunda consulta: Redis (incluso con []).
    first = client.get("/users")
    assert first.status_code == 200
    assert first.json() == []
    assert first.headers["X-Cache"] == "MISS"
    assert client.get("/users").headers["X-Cache"] == "HIT"
    assert 0 < service.cache.ttl(CACHE_KEY) <= CACHE_TTL

    created = client.post(
        "/users", json={"name": "Ana", "email": "ana@example.com"}
    )
    assert created.status_code == 201
    assert service.cache.get(CACHE_KEY) is None  # POST invalidó la caché.

    fresh = client.get("/users")
    assert fresh.headers["X-Cache"] == "MISS"
    assert fresh.json() == [created.json()]
    assert client.get("/users").headers["X-Cache"] == "HIT"


def test_duplicate_email_and_validation(client):
    user = {"name": "Ana", "email": "ana@example.com"}
    assert client.post("/users", json=user).status_code == 201
    assert client.post("/users", json=user).status_code == 409
    invalid = {"name": "", "email": "not-an-email"}
    assert client.post("/users", json=invalid).status_code == 422
