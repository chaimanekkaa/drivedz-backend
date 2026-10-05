import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401  (enregistre toutes les tables)
from app.config import DEFAULT_SECRET, settings
from app.routers import auth, exams, notifications, payments, planning, settings as settings_router, users, vehicles

logger = logging.getLogger("uvicorn.error")

if settings.secret_key == DEFAULT_SECRET or len(settings.secret_key) < 32:
    logger.warning("SECRET_KEY faible ou par défaut : générez-en une longue (python -c \"import secrets; print(secrets.token_urlsafe(48))\").")

# Le schéma de la base est géré par Alembic :  alembic upgrade head
app = FastAPI(title="DriveDZ API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth, users, planning, vehicles, payments, exams, settings_router, notifications):
    app.include_router(r.router)


@app.get("/")
def root():
    return {"status": "ok", "app": "DriveDZ API"}


@app.get("/health")
def health():
    return {"status": "ok"}
