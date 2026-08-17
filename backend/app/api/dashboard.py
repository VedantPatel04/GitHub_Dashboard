from fastapi import APIRouter
from app.schemas.dashboard import Dashboard

router = APIRouter(prefix="/api")

@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard() -> Dashboard:
    return Dashboard({
        "commit_count": 100,
        "pr_opened_count": 50,
        "pr_merged_count": 30,
        "active_repo_count": 20,
    }) #temporary hard-coded response to test if APIRouter works.

    