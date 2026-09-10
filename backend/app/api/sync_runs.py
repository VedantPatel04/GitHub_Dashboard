from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.models.SyncRun import SyncRun
from app.models.user import User
from app.schemas.sync_run import SyncRunPublic
from app.services.sync import run_sync

router = APIRouter(prefix="/api")


@router.post("/sync-runs", response_model=SyncRunPublic)
def create_sync_run(request: Request, db: Session = Depends(get_db)) -> SyncRun:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not user.access_token:
        raise HTTPException(status_code=503, detail="No GitHub access token stored")

    run = SyncRun(
        status="running",
        started_at=datetime.now(timezone.utc),
        finished_at=None,
        error_message=None,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        failures = run_sync(db, user.access_token)
        allowlist_len = len(get_settings().github_repo_list())
        if not failures:
            run.status = "success"
            run.error_message = None
        elif allowlist_len and len(failures) >= allowlist_len:
            run.status = "failed"
            run.error_message = "\n".join(failures)
        else:
            run.status = "partial"
            run.error_message = "\n".join(failures)
    except Exception as exc:
        run.status = "failed"
        run.error_message = f"{type(exc).__name__}: {exc}"
    finally:
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)

    return run
