import pytest
import httpx
from sqlalchemy import select

from app.config import get_settings
from app.db.session import SessionLocal
from app.models.user import User
from app.services.github_client import (
    get_authenticated_user,
    get_repository,
    list_commits,
)


@pytest.mark.live
def test_github_client_with_token_from_postgres() -> None:
    db = SessionLocal() #opens a db session 
    try:
        user = db.execute(select(User)).scalars().first() 
    finally:
        db.close()

    if user is None or not user.access_token:
        pytest.skip("No users.access_token in Postgres - complete GitHub OAuth first")

    token = user.access_token
    try:
        profile = get_authenticated_user(token)
    except httpx.HTTPStatusError as exc:
        if exc.response is not None and exc.response.status_code == 401:
            pytest.skip(
                "Stored token was rejected by GitHub (401). "
                "Log in again at /api/auth/github, then re-run: pytest -m live"
            )
        raise

    assert profile["id"] == user.github_id
    assert profile["login"] == user.login
    owner, name = get_settings().github_repo_list()[0].split("/")
    repo = get_repository(token, owner, name)
    assert repo["id"]
    assert repo["name"] == name
    assert repo["owner"]["login"] == owner
    assert repo["full_name"] == f"{owner}/{name}"
    assert repo["default_branch"]

    commits = list_commits(
        token,
        owner,
        name,
        sha=repo["default_branch"],
        max_pages=1,
    )
    assert isinstance(commits, list)
    if commits:
        assert "sha" in commits[0]
