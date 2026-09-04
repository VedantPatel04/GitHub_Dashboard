from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.ActivityEvent import ActivityEvent
from app.models.repositories import Repository
from app.models.SyncRun import SyncRun
from app.models.user import User
from app.services.sync import (
    normalize_commit,
    run_sync,
    upsert_commits,
    upsert_repository,
)

# GitHub list-commits items include many sibling fields. The decoys below are
# real keys from that payload; they must NOT be the source of mapped columns.
_API_URL = "https://api.github.com/repos/octocat/Hello-World/commits/6dcb09b5b57875f334f61aebed695e2e4193db5e"
_HTML_URL = "https://github.com/octocat/Hello-World/commit/6dcb09b5b57875f334f61aebed695e2e4193db5e"
_AUTHOR_DATE = "2011-04-14T16:00:49Z"
_COMMITTER_DATE = "2011-04-14T17:30:00Z"  # later than author; mapper must ignore this
_GIT_AUTHOR_NAME = "Monalisa Octocat"
_WEB_FLOW_LOGIN = "web-flow"
_SHA = "6dcb09b5b57875f334f61aebed695e2e4193db5e"
_GITHUB_REPO_ID = 1296269
_LOCAL_REPOSITORY_ID = 3
_DEFAULT_AUTHOR: dict[str, Any] = {"login": "octocat", "id": 1, "type": "User"}


def _github_list_commits_item(
    *,
    sha: str = _SHA,
    html_url: str = _HTML_URL,
    message: str = "Fix all the bugs",
    author_date: str = _AUTHOR_DATE,
    author: dict[str, Any] | None = _DEFAULT_AUTHOR,
) -> dict[str, Any]:
    """Shape of one object from GET /repos/{owner}/{name}/commits."""
    return {
        "sha": sha,
        "url": _API_URL,
        "html_url": html_url,
        "comments_url": f"{_API_URL}/comments",
        "author": author,
        "committer": {"login": _WEB_FLOW_LOGIN, "id": 19864447, "type": "User"},
        "commit": {
            "url": f"https://api.github.com/repos/octocat/Hello-World/git/commits/{sha}",
            "message": message,
            "comment_count": 0,
            "author": {
                "name": _GIT_AUTHOR_NAME,
                "email": "support@github.com",
                "date": author_date,
            },
            "committer": {
                "name": "GitHub",
                "email": "noreply@github.com",
                "date": _COMMITTER_DATE,
            },
        },
    }


def test_normalize_commit_maps_every_activity_event_column() -> None:
    commit = _github_list_commits_item()

    event = normalize_commit(
        commit,
        github_repo_id=_GITHUB_REPO_ID,
        repository_id=_LOCAL_REPOSITORY_ID,
    )

    assert event.external_key == f"commit:{_GITHUB_REPO_ID}:{_SHA}"
    assert event.event_type == "commit"
    assert event.html_url == _HTML_URL
    assert event.html_url != commit["url"]
    assert event.occurred_at == datetime(2011, 4, 14, 16, 0, 49, tzinfo=timezone.utc)
    assert event.occurred_at != datetime(2011, 4, 14, 17, 30, 0, tzinfo=timezone.utc)
    assert event.author_login == "octocat"
    assert event.author_login != _GIT_AUTHOR_NAME
    assert event.author_login != _WEB_FLOW_LOGIN
    assert event.repository_id == _LOCAL_REPOSITORY_ID
    assert event.repository_id != _GITHUB_REPO_ID
    assert event.message == "Fix all the bugs"


def test_normalize_commit_null_author_does_not_use_git_name() -> None:
    """GitHub sets author to null when the git email matches no account."""
    commit = _github_list_commits_item(author=None)

    event = normalize_commit(
        commit,
        github_repo_id=_GITHUB_REPO_ID,
        repository_id=_LOCAL_REPOSITORY_ID,
    )

    assert event.author_login is None
    assert event.author_login != _GIT_AUTHOR_NAME
    assert event.external_key == f"commit:{_GITHUB_REPO_ID}:{_SHA}"
    assert event.html_url == _HTML_URL
    assert event.occurred_at == datetime(2011, 4, 14, 16, 0, 49, tzinfo=timezone.utc)
    assert event.repository_id == _LOCAL_REPOSITORY_ID
    assert event.message == "Fix all the bugs"


def test_normalize_commit_external_key_interpolates_repo_id_and_sha() -> None:
    commit_a = _github_list_commits_item(sha="a" * 40)
    commit_b = _github_list_commits_item(sha="b" * 40)

    event_a = normalize_commit(commit_a, github_repo_id=11, repository_id=1)
    event_b = normalize_commit(commit_b, github_repo_id=22, repository_id=1)

    assert event_a.external_key == f"commit:11:{'a' * 40}"
    assert event_b.external_key == f"commit:22:{'b' * 40}"
    assert event_a.external_key != event_b.external_key
    assert event_a.repository_id == event_b.repository_id == 1


def test_normalize_commit_keeps_bot_login_verbatim() -> None:
    commit = _github_list_commits_item(
        author={"login": "dependabot[bot]", "id": 49699333, "type": "Bot"},
    )

    event = normalize_commit(commit, github_repo_id=_GITHUB_REPO_ID, repository_id=1)

    assert event.author_login == "dependabot[bot]"


@pytest.mark.parametrize(
    "message",
    [
        "",
        "Fix all the bugs",
        "subject\n\nbody line 1\nbody line 2",
    ],
)
def test_normalize_commit_preserves_commit_message_exactly(message: str) -> None:
    commit = _github_list_commits_item(message=message)

    event = normalize_commit(commit, github_repo_id=_GITHUB_REPO_ID, repository_id=1)

    assert event.message == message
    assert event.message is not None


def test_normalize_commit_parses_github_zulu_timestamp() -> None:
    """GitHub documents timestamps as YYYY-MM-DDTHH:MM:SSZ."""
    commit = _github_list_commits_item(author_date="2024-06-02T08:05:09Z")

    event = normalize_commit(commit, github_repo_id=_GITHUB_REPO_ID, repository_id=1)

    assert event.occurred_at == datetime(2024, 6, 2, 8, 5, 9, tzinfo=timezone.utc)
    assert event.occurred_at.tzinfo is timezone.utc


def _github_get_repository_payload(
    *,
    github_id: int = _GITHUB_REPO_ID,
    name: str = "Hello-World",
    owner_login: str = "octocat",
    private: bool = False,
    default_branch: str = "master",
) -> dict[str, Any]:
    """Shape of GET /repos/{owner}/{name}. Extra keys are real GitHub fields
    that must not be treated as the repo's identity.
    """
    full_name = f"{owner_login}/{name}"
    return {
        "id": github_id,
        "node_id": "MDEwOlJlcG9zaXRvcnkxMjk2MjY5",
        "name": name,
        "full_name": full_name,
        "private": private,
        "owner": {
            "login": owner_login,
            "id": 1,
            "node_id": "MDQ6VXNlcjE=",
            "type": "User",
            "site_admin": False,
        },
        "html_url": f"https://github.com/{full_name}",
        "description": "This your first repo!",
        "fork": False,
        "url": f"https://api.github.com/repos/{full_name}",
        "default_branch": default_branch,
        "organization": {"login": "github", "id": 9919, "type": "Organization"},
    }


@pytest.fixture
def db() -> Session:
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

    # Register every model on Base.metadata before create_all.
    _ = (User, Repository, ActivityEvent, SyncRun)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def _repo_count(db: Session) -> int:
    return db.execute(select(func.count()).select_from(Repository)).scalar_one()


def _event_count(db: Session) -> int:
    return db.execute(select(func.count()).select_from(ActivityEvent)).scalar_one()


def test_upsert_repository_inserts_using_github_id_field(db: Session) -> None:
    payload = _github_get_repository_payload()

    repo = upsert_repository(db, payload)
    db.commit()

    assert repo.id is not None
    assert repo.github_id == _GITHUB_REPO_ID
    assert repo.github_id == payload["id"]
    assert repo.name == "Hello-World"
    assert repo.owner_login == "octocat"
    assert repo.owner_login != payload["organization"]["login"]
    assert repo.full_name == "octocat/Hello-World"
    assert repo.private is False
    assert repo.html_url == "https://github.com/octocat/Hello-World"
    assert repo.default_branch == "master"
    assert _repo_count(db) == 1


def test_upsert_repository_ignores_github_id_json_key_if_present(db: Session) -> None:
    """GitHub's repo object uses `id`, not `github_id`. A decoy must not win."""
    payload = _github_get_repository_payload(github_id=42)
    payload["github_id"] = 999_999

    repo = upsert_repository(db, payload)
    db.commit()

    assert repo.github_id == 42
    assert repo.github_id != payload["github_id"]


def test_upsert_repository_second_call_same_github_id_does_not_insert(db: Session) -> None:
    first = upsert_repository(db, _github_get_repository_payload())
    db.commit()
    local_id = first.id

    second = upsert_repository(db, _github_get_repository_payload())
    db.commit()

    assert second.id == local_id
    assert _repo_count(db) == 1


def test_upsert_repository_updates_display_fields_on_rename(db: Session) -> None:
    upsert_repository(db, _github_get_repository_payload())
    db.commit()

    renamed = _github_get_repository_payload(name="Hello-Universe")
    assert renamed["id"] == _GITHUB_REPO_ID
    repo = upsert_repository(db, renamed)
    db.commit()

    assert _repo_count(db) == 1
    assert repo.github_id == _GITHUB_REPO_ID
    assert repo.name == "Hello-Universe"
    assert repo.full_name == "octocat/Hello-Universe"
    assert repo.html_url == "https://github.com/octocat/Hello-Universe"


def test_upsert_repository_distinct_github_ids_are_distinct_rows(db: Session) -> None:
    upsert_repository(db, _github_get_repository_payload(github_id=1, name="A"))
    upsert_repository(db, _github_get_repository_payload(github_id=2, name="B"))
    db.commit()

    assert _repo_count(db) == 2


def test_upsert_repository_persists_private_true(db: Session) -> None:
    repo = upsert_repository(
        db, _github_get_repository_payload(private=True, default_branch="main")
    )
    db.commit()

    assert repo.private is True
    assert repo.default_branch == "main"


def test_upsert_repository_requires_github_id_key(db: Session) -> None:
    payload = _github_get_repository_payload()
    del payload["id"]

    with pytest.raises(KeyError):
        upsert_repository(db, payload)


def test_upsert_commits_inserts_normalized_events(db: Session) -> None:
    repo = upsert_repository(db, _github_get_repository_payload())
    db.commit()

    upsert_commits(
        db,
        [_github_list_commits_item()],
        github_repo_id=_GITHUB_REPO_ID,
        repository_id=repo.id,
    )
    db.commit()

    event = db.execute(select(ActivityEvent)).scalar_one()
    assert event.external_key == f"commit:{_GITHUB_REPO_ID}:{_SHA}"
    assert event.event_type == "commit"
    assert event.html_url == _HTML_URL
    assert event.author_login == "octocat"
    assert event.repository_id == repo.id
    assert event.message == "Fix all the bugs"
    assert _event_count(db) == 1


def test_upsert_commits_second_sync_does_not_duplicate_or_rewrite(db: Session) -> None:
    repo = upsert_repository(db, _github_get_repository_payload())
    db.commit()

    first = _github_list_commits_item(message="original")
    upsert_commits(
        db, [first], github_repo_id=_GITHUB_REPO_ID, repository_id=repo.id
    )
    db.commit()
    event_id = db.execute(select(ActivityEvent)).scalar_one().id

    rewritten = _github_list_commits_item(message="should not replace original")
    upsert_commits(
        db, [rewritten], github_repo_id=_GITHUB_REPO_ID, repository_id=repo.id
    )
    db.commit()

    event = db.execute(select(ActivityEvent)).scalar_one()
    assert _event_count(db) == 1
    assert event.id == event_id
    assert event.message == "original"


def test_upsert_commits_same_sha_different_repo_ids_are_distinct(db: Session) -> None:
    repo_a = upsert_repository(db, _github_get_repository_payload(github_id=11, name="A"))
    repo_b = upsert_repository(db, _github_get_repository_payload(github_id=22, name="B"))
    db.commit()

    commit = _github_list_commits_item()
    upsert_commits(db, [commit], github_repo_id=11, repository_id=repo_a.id)
    upsert_commits(db, [commit], github_repo_id=22, repository_id=repo_b.id)
    db.commit()

    keys = {
        row.external_key
        for row in db.execute(select(ActivityEvent)).scalars()
    }
    assert keys == {f"commit:11:{_SHA}", f"commit:22:{_SHA}"}
    assert _event_count(db) == 2


def test_upsert_commits_duplicate_sha_in_same_batch_inserts_once(db: Session) -> None:
    repo = upsert_repository(db, _github_get_repository_payload())
    db.commit()

    upsert_commits(
        db,
        [_github_list_commits_item(), _github_list_commits_item()],
        github_repo_id=_GITHUB_REPO_ID,
        repository_id=repo.id,
    )
    db.commit()

    assert _event_count(db) == 1


def test_upsert_commits_null_author_is_stored(db: Session) -> None:
    repo = upsert_repository(db, _github_get_repository_payload())
    db.commit()

    upsert_commits(
        db,
        [_github_list_commits_item(author=None)],
        github_repo_id=_GITHUB_REPO_ID,
        repository_id=repo.id,
    )
    db.commit()

    event = db.execute(select(ActivityEvent)).scalar_one()
    assert event.author_login is None


def test_upsert_commits_empty_list_is_noop(db: Session) -> None:
    repo = upsert_repository(db, _github_get_repository_payload())
    db.commit()

    upsert_commits(
        db, [], github_repo_id=_GITHUB_REPO_ID, repository_id=repo.id
    )
    db.commit()

    assert _event_count(db) == 0


def test_upsert_commits_rejects_unknown_repository_id(db: Session) -> None:
    with pytest.raises(Exception):
        upsert_commits(
            db,
            [_github_list_commits_item()],
            github_repo_id=_GITHUB_REPO_ID,
            repository_id=9_999_999,
        )
        db.commit()


def _settings_allowlist(*full_names: str) -> MagicMock:
    settings = MagicMock()
    settings.github_repo_list.return_value = list(full_names)
    return settings


def test_run_sync_upserts_allowlisted_repo_and_default_branch_commits(db: Session) -> None:
    payload = _github_get_repository_payload()
    commits = [_github_list_commits_item()]

    with (
        patch("app.services.sync.get_settings", return_value=_settings_allowlist("octocat/Hello-World")),
        patch("app.services.sync.get_repository", return_value=payload) as mock_repo,
        patch("app.services.sync.list_commits", return_value=commits) as mock_commits,
    ):
        failures = run_sync(db, "user-token-from-db")

    assert failures == []
    mock_repo.assert_called_once_with("user-token-from-db", "octocat", "Hello-World")
    mock_commits.assert_called_once_with(
        "user-token-from-db",
        "octocat",
        "Hello-World",
        sha="master",
    )
    assert _repo_count(db) == 1
    assert _event_count(db) == 1
    stored = db.execute(select(Repository)).scalar_one()
    assert stored.github_id == payload["id"]


def test_run_sync_second_pass_does_not_increase_event_count(db: Session) -> None:
    payload = _github_get_repository_payload()
    commits = [_github_list_commits_item()]
    allow = _settings_allowlist("octocat/Hello-World")

    with (
        patch("app.services.sync.get_settings", return_value=allow),
        patch("app.services.sync.get_repository", return_value=payload),
        patch("app.services.sync.list_commits", return_value=commits),
    ):
        assert run_sync(db, "token") == []
        first_count = _event_count(db)
        assert run_sync(db, "token") == []

    assert first_count == 1
    assert _event_count(db) == 1


def test_run_sync_continues_after_one_repo_error_and_keeps_successful_rows(
    db: Session,
) -> None:
    ok_payload = _github_get_repository_payload(github_id=1, name="Hello-World")
    ok_commits = [_github_list_commits_item(sha="a" * 40)]

    def _get_repository(_token: str, owner: str, name: str) -> dict[str, Any]:
        if name == "missing":
            raise ConnectionError("GitHub 404 simulated")
        return ok_payload

    with (
        patch(
            "app.services.sync.get_settings",
            return_value=_settings_allowlist(
                "octocat/Hello-World", "octocat/missing"
            ),
        ),
        patch("app.services.sync.get_repository", side_effect=_get_repository),
        patch("app.services.sync.list_commits", return_value=ok_commits),
    ):
        failures = run_sync(db, "token")

    assert len(failures) == 1
    assert failures[0].startswith("octocat/missing: ConnectionError:")
    assert "token" not in failures[0]
    assert _repo_count(db) == 1
    assert db.execute(select(Repository)).scalar_one().name == "Hello-World"
    assert _event_count(db) == 1


def test_run_sync_rolls_back_repo_if_list_commits_fails(db: Session) -> None:
    payload = _github_get_repository_payload()

    with (
        patch(
            "app.services.sync.get_settings",
            return_value=_settings_allowlist("octocat/Hello-World"),
        ),
        patch("app.services.sync.get_repository", return_value=payload),
        patch(
            "app.services.sync.list_commits",
            side_effect=RuntimeError("rate limited"),
        ),
    ):
        failures = run_sync(db, "token")

    assert len(failures) == 1
    assert "octocat/Hello-World" in failures[0]
    assert "RuntimeError" in failures[0]
    assert _repo_count(db) == 0
    assert _event_count(db) == 0


def test_run_sync_empty_allowlist_is_full_success(db: Session) -> None:
    with patch(
        "app.services.sync.get_settings",
        return_value=_settings_allowlist(),
    ):
        failures = run_sync(db, "token")

    assert failures == []
    assert _repo_count(db) == 0
    assert _event_count(db) == 0


def test_run_sync_all_repos_failing_returns_a_failure_per_repo(db: Session) -> None:
    with (
        patch(
            "app.services.sync.get_settings",
            return_value=_settings_allowlist("a/one", "b/two"),
        ),
        patch(
            "app.services.sync.get_repository",
            side_effect=RuntimeError("down"),
        ),
    ):
        failures = run_sync(db, "token")

    assert len(failures) == 2
    assert failures[0].startswith("a/one:")
    assert failures[1].startswith("b/two:")
    assert _repo_count(db) == 0


def test_upsert_repository_updates_private_and_default_branch(db: Session) -> None:
    upsert_repository(
        db, _github_get_repository_payload(private=False, default_branch="master")
    )
    db.commit()

    repo = upsert_repository(
        db, _github_get_repository_payload(private=True, default_branch="main")
    )
    db.commit()

    assert _repo_count(db) == 1
    assert repo.private is True
    assert repo.default_branch == "main"


def test_upsert_repository_missing_owner_raises(db: Session) -> None:
    payload = _github_get_repository_payload()
    del payload["owner"]

    with pytest.raises(KeyError):
        upsert_repository(db, payload)


def test_run_sync_first_repo_fails_second_still_upserts(db: Session) -> None:
    ok_payload = _github_get_repository_payload(github_id=1, name="Hello-World")
    ok_commits = [_github_list_commits_item(sha="a" * 40)]

    def _get_repository(_token: str, owner: str, name: str) -> dict[str, Any]:
        if name == "missing":
            raise ConnectionError("GitHub 404 simulated")
        return ok_payload

    with (
        patch(
            "app.services.sync.get_settings",
            return_value=_settings_allowlist(
                "octocat/missing", "octocat/Hello-World"
            ),
        ),
        patch("app.services.sync.get_repository", side_effect=_get_repository),
        patch("app.services.sync.list_commits", return_value=ok_commits) as mock_commits,
    ):
        failures = run_sync(db, "token")

    assert len(failures) == 1
    assert failures[0].startswith("octocat/missing:")
    mock_commits.assert_called_once()
    assert _repo_count(db) == 1
    assert _event_count(db) == 1


def test_run_sync_prior_repo_survives_later_list_commits_failure(db: Session) -> None:
    payload_a = _github_get_repository_payload(github_id=11, name="A")
    payload_b = _github_get_repository_payload(github_id=22, name="B")

    def _get_repository(_token: str, owner: str, name: str) -> dict[str, Any]:
        return payload_a if name == "A" else payload_b

    def _list_commits(
        _token: str, owner: str, name: str, *, sha: str | None = None, **_kwargs: Any
    ) -> list[dict[str, Any]]:
        if name == "B":
            raise RuntimeError("rate limited")
        return [_github_list_commits_item(sha="a" * 40)]

    with (
        patch(
            "app.services.sync.get_settings",
            return_value=_settings_allowlist("octocat/A", "octocat/B"),
        ),
        patch("app.services.sync.get_repository", side_effect=_get_repository),
        patch("app.services.sync.list_commits", side_effect=_list_commits),
    ):
        failures = run_sync(db, "token")

    assert len(failures) == 1
    assert failures[0].startswith("octocat/B: RuntimeError:")
    assert _repo_count(db) == 1
    assert db.execute(select(Repository)).scalar_one().name == "A"
    assert _event_count(db) == 1


def test_run_sync_skips_list_commits_when_get_repository_fails(db: Session) -> None:
    with (
        patch(
            "app.services.sync.get_settings",
            return_value=_settings_allowlist("octocat/missing"),
        ),
        patch(
            "app.services.sync.get_repository",
            side_effect=ConnectionError("GitHub 404 simulated"),
        ),
        patch("app.services.sync.list_commits") as mock_commits,
    ):
        failures = run_sync(db, "token")

    assert len(failures) == 1
    mock_commits.assert_not_called()
    assert _repo_count(db) == 0
    assert _event_count(db) == 0


def test_run_sync_malformed_commit_rolls_back_that_repo_only(db: Session) -> None:
    payload_ok = _github_get_repository_payload(github_id=11, name="A")
    payload_bad = _github_get_repository_payload(github_id=22, name="B")

    def _get_repository(_token: str, owner: str, name: str) -> dict[str, Any]:
        return payload_ok if name == "A" else payload_bad

    def _list_commits(
        _token: str, owner: str, name: str, *, sha: str | None = None, **_kwargs: Any
    ) -> list[dict[str, Any]]:
        if name == "B":
            return [{"html_url": "https://example.com/missing-sha"}]
        return [_github_list_commits_item(sha="a" * 40)]

    with (
        patch(
            "app.services.sync.get_settings",
            return_value=_settings_allowlist("octocat/A", "octocat/B"),
        ),
        patch("app.services.sync.get_repository", side_effect=_get_repository),
        patch("app.services.sync.list_commits", side_effect=_list_commits),
    ):
        failures = run_sync(db, "token")

    assert len(failures) == 1
    assert failures[0].startswith("octocat/B: KeyError:")
    assert _repo_count(db) == 1
    assert db.execute(select(Repository)).scalar_one().name == "A"
    assert _event_count(db) == 1


def test_upsert_repository_uses_html_url_not_api_url(db: Session) -> None:
    payload = _github_get_repository_payload()

    repo = upsert_repository(db, payload)
    db.commit()

    assert repo.html_url == payload["html_url"]
    assert repo.html_url != payload["url"]


def test_upsert_repository_missing_owner_login_raises(db: Session) -> None:
    payload = _github_get_repository_payload()
    del payload["owner"]["login"]

    with pytest.raises(KeyError):
        upsert_repository(db, payload)


def test_upsert_commits_persists_occurred_at_from_git_author_date(db: Session) -> None:
    repo = upsert_repository(db, _github_get_repository_payload())
    db.commit()

    upsert_commits(
        db,
        [_github_list_commits_item()],
        github_repo_id=_GITHUB_REPO_ID,
        repository_id=repo.id,
    )
    db.commit()

    event = db.execute(select(ActivityEvent)).scalar_one()
    stored = event.occurred_at.replace(tzinfo=None)
    assert stored == datetime(2011, 4, 14, 16, 0, 49)
    assert stored != datetime(2011, 4, 14, 17, 30, 0)


def test_run_sync_empty_commit_list_still_persists_repo(db: Session) -> None:
    payload = _github_get_repository_payload()

    with (
        patch(
            "app.services.sync.get_settings",
            return_value=_settings_allowlist("octocat/Hello-World"),
        ),
        patch("app.services.sync.get_repository", return_value=payload),
        patch("app.services.sync.list_commits", return_value=[]),
    ):
        failures = run_sync(db, "token")

    assert failures == []
    assert _repo_count(db) == 1
    assert _event_count(db) == 0


def test_run_sync_passes_each_repo_default_branch_as_sha(db: Session) -> None:
    payload_a = _github_get_repository_payload(
        github_id=11, name="A", default_branch="master"
    )
    payload_b = _github_get_repository_payload(
        github_id=22, name="B", default_branch="main"
    )

    def _get_repository(_token: str, owner: str, name: str) -> dict[str, Any]:
        return payload_a if name == "A" else payload_b

    with (
        patch(
            "app.services.sync.get_settings",
            return_value=_settings_allowlist("octocat/A", "octocat/B"),
        ),
        patch("app.services.sync.get_repository", side_effect=_get_repository),
        patch("app.services.sync.list_commits", return_value=[]) as mock_commits,
    ):
        assert run_sync(db, "token") == []

    assert mock_commits.call_args_list[0].kwargs["sha"] == "master"
    assert mock_commits.call_args_list[1].kwargs["sha"] == "main"


def test_run_sync_event_key_uses_github_repo_id_not_local_pk(db: Session) -> None:
    payload = _github_get_repository_payload(github_id=_GITHUB_REPO_ID)
    commits = [_github_list_commits_item()]

    with (
        patch(
            "app.services.sync.get_settings",
            return_value=_settings_allowlist("octocat/Hello-World"),
        ),
        patch("app.services.sync.get_repository", return_value=payload),
        patch("app.services.sync.list_commits", return_value=commits),
    ):
        assert run_sync(db, "token") == []

    event = db.execute(select(ActivityEvent)).scalar_one()
    repo = db.execute(select(Repository)).scalar_one()
    assert event.external_key == f"commit:{_GITHUB_REPO_ID}:{_SHA}"
    assert event.repository_id == repo.id
    assert event.repository_id != _GITHUB_REPO_ID
    assert repo.github_id == _GITHUB_REPO_ID
