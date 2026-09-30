import json
import logging

from redis import Redis
from redis.exceptions import RedisError

from app import database
from app.config import CACHE_KEY, CACHE_TTL, REDIS_URL

logger = logging.getLogger(__name__)
cache = Redis.from_url(
    REDIS_URL, decode_responses=True, socket_connect_timeout=1, socket_timeout=1
)


def get_users():
    """Cache-aside: consultar Redis; si no hay caché, consultar PostgreSQL."""
    try:
        cached = cache.get(CACHE_KEY)
        if cached is not None:  # Incluso una lista vacía [] es una caché válida.
            return json.loads(cached), "HIT"
    except RedisError:
        logger.warning("Redis no disponible; se consultará PostgreSQL")

    users = database.list_users()
    try:
        cache.set(CACHE_KEY, json.dumps(users), ex=CACHE_TTL)
    except RedisError:
        logger.warning("No se pudo guardar la caché")
    return users, "MISS"


def create_user(name: str, email: str):
    user = database.insert_user(name, email)
    # Primero guardar en PostgreSQL, luego invalidar la lista en Redis.
    try:
        cache.delete(CACHE_KEY)
    except RedisError:
        logger.warning("No se pudo invalidar la caché; expirará por TTL")
    return user
