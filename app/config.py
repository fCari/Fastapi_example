import os

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://app:app@localhost:5432/users"
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_KEY = os.getenv("CACHE_KEY", "users:all")
CACHE_TTL = 60
