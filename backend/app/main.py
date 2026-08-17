from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.dashboard import router as dashboard_router

app = FastAPI(title="GitHub Dashboard API")

app.include_router(health_router)
app.include_router(dashboard_router)