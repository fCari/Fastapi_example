import psycopg
from psycopg.rows import dict_row

from app.config import DATABASE_URL


def connect():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=5)


def init_db():
    # Para el laboratorio. En proyectos reales se usan migraciones.
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL
            )
        """)


def list_users():
    with connect() as conn:
        return conn.execute("SELECT id, name, email FROM users ORDER BY id").fetchall()


def insert_user(name: str, email: str):
    # Los valores se pasan como parámetros, nunca se concatenan al SQL.
    with connect() as conn:
        user = conn.execute(
            "INSERT INTO users (name, email) VALUES (%s, %s) RETURNING id, name, email",
            (name, email),
        ).fetchone()
    # Al salir del contexto se confirma la transacción antes de retornar.
    return user
