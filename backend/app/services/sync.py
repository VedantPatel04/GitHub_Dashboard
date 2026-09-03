from datetime import datetime
from typing import Any

from app.models.ActivityEvent import ActivityEvent


def commit_to_event(commit: dict[str, Any], github_repo_id: int, repository_id: int) -> ActivityEvent:
    #commit is a dict from GH's GET /repos/{owner}/{repo}/commits
    #github_repo_id is repo id from get_repository
    #Postgres row  - repositories.id
    """helper function: Map one GitHub commit JSON object to an ActivityEvent"""
    
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
