from datetime import datetime
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.ActivityEvent import ActivityEvent
from app.models.repositories import Repository
from app.services.github_client import get_repository, list_commits

logger = logging.getLogger(__name__)


def normalize_commit(commit: dict[str, Any], github_repo_id: int, repository_id: int) -> ActivityEvent:
    #commit is a dict from GH's GET /repos/{owner}/{repo}/commits
    #github_repo_id is repo id from get_repository
    #Postgres row  - repositories.id
    """helper function: Map one GitHub commit JSON object to an ActivityEvent
        
       DOES NOT write to the db """
    
    occurred_at = datetime.fromisoformat(
        commit["commit"]["author"]["date"].replace("Z", "+00:00")
    )
    return ActivityEvent(
        external_key=f"commit:{github_repo_id}:{commit['sha']}",
        event_type="commit",
        html_url=commit["html_url"],
        occurred_at=occurred_at,
        author_login=commit["author"]["login"] if commit["author"] is not None else None,
        repository_id=repository_id,
        message=commit["commit"]["message"],
    )


def upsert_repository(db: Session, repository: dict[str, Any]) -> Repository:
    """Insert or update a row keyed by GitHub's repo id (`repository["id"]`).

    ActivityEvent.repository_id is a FK to repositories.id, so this row
    must exist before commits are stored. Does NOT commit to db gang!! the caller owns
    the transaction (run_sync commits per allowlisted repo)
    """
    github_id = repository["id"]  # GitHub's repo object uses `id`, not `github_id`
    # Suggestion: select-then-write is sound. A concurrent double-insert hits
    # UniqueConstraint(github_id) and run_sync records it as a failure.
    # ON CONFLICT DO NOTHING would skip the rename updates in the else branch.
    repo = db.execute(
        select(Repository).where(Repository.github_id == github_id)
    ).scalar_one_or_none()

    owner_login = repository["owner"]["login"]

    if repo is None:
        repo = Repository(
            github_id=github_id,
            name=repository["name"],
            owner_login=owner_login,
            full_name=repository["full_name"],
            private=repository["private"],
            html_url=repository["html_url"],
            default_branch=repository["default_branch"],
        )
        db.add(repo)
    else:
        repo.name = repository["name"]
        repo.owner_login = owner_login
        repo.full_name = repository["full_name"]
        repo.private = repository["private"]
        repo.html_url = repository["html_url"]
        repo.default_branch = repository["default_branch"]

    db.flush()
    db.refresh(repo)
    return repo


def upsert_commits(db: Session, commits: list[dict[str, Any]],*, github_repo_id: int, repository_id: int,) -> None:
    """Insert ActivityEvent rows as commits -  skip any whose external_key (or sha) already exists

    does not update existing event 
    Does not commit - for same reason as above
    """
    seen: set[str] = set()
    for commit in commits:
        event = normalize_commit(commit, github_repo_id, repository_id)
        if event.external_key in seen:
            continue
        seen.add(event.external_key)
        existing = db.execute(
            select(ActivityEvent).where(
                ActivityEvent.external_key == event.external_key
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(event)
    db.flush()


def run_sync(db: Session, token: str) -> list[str]:
    """Backfill allowlisted repos - Returns one failure string per repo that errored.

    Empty list means every repository in the allowlist succeeded. The HTTP route maps
    this list to SyncRun status (success / partial / failed) - this function
    does not set status.
    """
    failures: list[str] = [] #repos that failed to load (sync)
    allowlist = get_settings().github_repo_list() # get allowlist from settings

    for full_name in allowlist:
        owner, name = full_name.split("/")
        try:
            repo_json = get_repository(token, owner, name)
            repo_row = upsert_repository(db, repo_json)
            commits = list_commits(
                token,
                owner,
                name,
                sha=repo_json["default_branch"],
            )
            upsert_commits(
                db,
                commits,
                github_repo_id=repo_json["id"],
                repository_id=repo_row.id,
            )
            db.commit()
            logger.info(
                "synced %s github_id=%s commits=%s",
                full_name,
                repo_json["id"],
                len(commits),
            )
        except Exception as exc:
            db.rollback()
            failures.append(f"{owner}/{name}: {type(exc).__name__}: {exc}")
            logger.exception("sync failed for %s", full_name)
            continue

    return failures
