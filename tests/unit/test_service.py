import json
from unittest.mock import Mock

from redis.exceptions import ConnectionError

from app import service
from app.config import CACHE_KEY, CACHE_TTL

USERS = [{"id": 1, "name": "Ana", "email": "ana@example.com"}]


def test_cache_hit_does_not_query_postgres(monkeypatch):
    cache = Mock()
    cache.get.return_value = json.dumps(USERS)
    query = Mock()
    monkeypatch.setattr(service, "cache", cache)
    monkeypatch.setattr(service.database, "list_users", query)

    assert service.get_users() == (USERS, "HIT")
    query.assert_not_called()


def test_cache_miss_queries_postgres_and_sets_ttl(monkeypatch):
    cache = Mock()
    cache.get.return_value = None
    query = Mock(return_value=USERS)
    monkeypatch.setattr(service, "cache", cache)
    monkeypatch.setattr(service.database, "list_users", query)

    assert service.get_users() == (USERS, "MISS")
    query.assert_called_once_with()
    cache.set.assert_called_once_with(CACHE_KEY, json.dumps(USERS), ex=CACHE_TTL)


def test_redis_failure_still_returns_users(monkeypatch):
    cache = Mock()
    cache.get.side_effect = ConnectionError("Redis offline")
    cache.set.side_effect = ConnectionError("Redis offline")
    monkeypatch.setattr(service, "cache", cache)
    monkeypatch.setattr(service.database, "list_users", Mock(return_value=USERS))

    assert service.get_users() == (USERS, "MISS")


def test_create_user_invalidates_cache(monkeypatch):
    cache = Mock()
    insert = Mock(return_value=USERS[0])
    monkeypatch.setattr(service, "cache", cache)
    monkeypatch.setattr(service.database, "insert_user", insert)

    assert service.create_user("Ana", "ana@example.com") == USERS[0]
    insert.assert_called_once_with("Ana", "ana@example.com")
    cache.delete.assert_called_once_with(CACHE_KEY)
