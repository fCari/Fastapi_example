from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response
from psycopg.errors import UniqueViolation

from app import database, service
from app.schemas import UserCreate, UserRead


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield
    service.cache.close()


app = FastAPI(title="Usuarios con PostgreSQL y Redis", lifespan=lifespan)


@app.get("/health")
def health():
    # Liveness: indica que la API responde, no verifica las dependencias.
    return {"status": "ok"}


@app.get("/users", response_model=list[UserRead])
def get_users(response: Response):
    users, source = service.get_users()
    response.headers["X-Cache"] = source
    return users


@app.post("/users", response_model=UserRead, status_code=201)
def create_user(user: UserCreate):
    try:
        return service.create_user(user.name, str(user.email))
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="El email ya existe") from None
