from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.health import router as health_router
from app.api.dashboard import router as dashboard_router
from app.api.auth import router as auth_router

from app.config import get_settings

settings = get_settings()

app = FastAPI(title="GitHub Dashboard API")

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
)

cors_origins = {
    settings.frontend_origin.rstrip("/"),
    "http://127.0.0.1:5173",
    "http://localhost:5173",
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(dashboard_router)
app.include_router(auth_router)