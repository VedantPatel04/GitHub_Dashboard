from __future__ import annotations

import json
from base64 import b64encode
from datetime import datetime
from typing import Iterator
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from app.api.sync_runs import router as sync_runs_router
from app.db.session import Base, get_db
from app.models.ActivityEvent import ActivityEvent
from app.models.SyncRun import SyncRun
from app.models.repositories import Repository
from app.models.user import User

SESSION_SECRET = "test-session-secret"


@pytest.fixture
def db() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_sqlite_fks(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    _ = (User, Repository, ActivityEvent, SyncRun)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def _client(db: Session) -> TestClient:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)
    app.include_router(sync_runs_router)

    def _override_db() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_db] = _override_db
    return TestClient(app)


def _session_cookie(user_id: int) -> str:
    signer = TimestampSigner(str(SESSION_SECRET))
    payload = b64encode(json.dumps({"user_id": user_id}).encode("utf-8"))
    return signer.sign(payload).decode("utf-8")


def _authed(client: TestClient, user_id: int) -> None:
    client.cookies.set("session", _session_cookie(user_id))


def _user(db: Session, *, token: str = "gho_stored_token") -> User:
    user = User(
        github_id=1,
        login="alice",
        avatar_url="https://example.com/a.png",
        access_token=token,
        updated_at=datetime.now(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _settings(*repos: str) -> MagicMock:
    settings = MagicMock()
    settings.github_repo_list.return_value = list(repos)
    return settings


def test_post_sync_runs_unauthorized_without_session(db: Session) -> None:
    response = _client(db).post("/api/sync-runs")
    assert response.status_code == 401
    assert db.execute(select(SyncRun)).scalars().first() is None


def test_post_sync_runs_unauthorized_if_user_row_missing(db: Session) -> None:
    client = _client(db)
    _authed(client, user_id=999)
    response = client.post("/api/sync-runs")
    assert response.status_code == 401
    assert db.execute(select(SyncRun)).scalars().first() is None


def test_post_sync_runs_503_if_token_missing(db: Session) -> None:
    user = _user(db, token="")
    client = _client(db)
    _authed(client, user.id)
    response = client.post("/api/sync-runs")
    assert response.status_code == 503
    assert db.execute(select(SyncRun)).scalars().first() is None


def test_post_sync_runs_success_does_not_call_github_in_the_route(db: Session) -> None:
    user = _user(db)
    client = _client(db)
    _authed(client, user.id)

    with (
        patch("app.api.sync_runs.run_sync", return_value=[]) as mock_sync,
        patch(
            "app.api.sync_runs.get_settings",
            return_value=_settings("octocat/Hello-World"),
        ),
    ):
        response = client.post("/api/sync-runs")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["error_message"] is None
    assert body["finished_at"] is not None
    mock_sync.assert_called_once()
    assert mock_sync.call_args.args[1] == "gho_stored_token"
    run = db.execute(select(SyncRun)).scalar_one()
    assert run.status == "success"
    assert run.finished_at is not None


def test_post_sync_runs_partial_when_some_repos_fail(db: Session) -> None:
    user = _user(db)
    client = _client(db)
    _authed(client, user.id)
    failures = ["octocat/missing: ConnectionError: GitHub 404 simulated"]

    with (
        patch("app.api.sync_runs.run_sync", return_value=failures),
        patch(
            "app.api.sync_runs.get_settings",
            return_value=_settings("octocat/Hello-World", "octocat/missing"),
        ),
    ):
        response = client.post("/api/sync-runs")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partial"
    assert body["error_message"] == failures[0]
    assert "gho_stored_token" not in body["error_message"]


def test_post_sync_runs_failed_when_every_allowlisted_repo_fails(db: Session) -> None:
    user = _user(db)
    client = _client(db)
    _authed(client, user.id)
    failures = [
        "a/one: RuntimeError: down",
        "b/two: RuntimeError: down",
    ]

    with (
        patch("app.api.sync_runs.run_sync", return_value=failures),
        patch(
            "app.api.sync_runs.get_settings",
            return_value=_settings("a/one", "b/two"),
        ),
    ):
        response = client.post("/api/sync-runs")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error_message"] == "\n".join(failures)


def test_post_sync_runs_unexpected_error_still_finalizes_row(db: Session) -> None:
    user = _user(db)
    client = _client(db)
    _authed(client, user.id)

    with patch(
        "app.api.sync_runs.run_sync",
        side_effect=RuntimeError("boom"),
    ):
        response = client.post("/api/sync-runs")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert "RuntimeError" in body["error_message"]
    assert "boom" in body["error_message"]
    run = db.execute(select(SyncRun)).scalar_one()
    assert run.status == "failed"
    assert run.finished_at is not None
    assert run.started_at is not None
