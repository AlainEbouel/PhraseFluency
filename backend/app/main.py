import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.core.model_registry import Base  # noqa: F401 ensures all models are registered
from app.modules.admin.router import router as admin_router
from app.modules.audio.router import router as audio_router
from app.modules.auth.router import router as auth_router
from app.modules.conversations.router import router as conversations_router
from app.modules.imports.router import router as imports_router
from app.modules.learning.router import router as learning_router
from app.modules.statistics.router import router as statistics_router
from app.modules.tests.router import router as tests_router
from app.modules.users.router import router as users_router
from app.modules.users.service import bootstrap_admin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("phrasefluency")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.admin_bootstrap_email and settings.admin_bootstrap_password:
        db = SessionLocal()
        try:
            bootstrap_admin(
                db, settings.admin_bootstrap_email, settings.admin_bootstrap_password
            )
        finally:
            db.close()
    yield


app = FastAPI(title="PhraseFluency API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(imports_router)
app.include_router(learning_router)
app.include_router(tests_router)
app.include_router(conversations_router)
app.include_router(audio_router)
app.include_router(statistics_router)
app.include_router(admin_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ready"}
