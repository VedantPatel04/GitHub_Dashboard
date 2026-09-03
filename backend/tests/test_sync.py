from datetime import datetime, timezone
from typing import Any

import pytest

from app.services.sync import commit_to_event

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


def test_commit_to_event_maps_every_activity_event_column() -> None:
    commit = _github_list_commits_item()

    event = commit_to_event(
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


def test_commit_to_event_null_author_does_not_use_git_name() -> None:
    """GitHub sets author to null when the git email matches no account."""
    commit = _github_list_commits_item(author=None)

    event = commit_to_event(
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


def test_commit_to_event_external_key_interpolates_repo_id_and_sha() -> None:
    commit_a = _github_list_commits_item(sha="a" * 40)
    commit_b = _github_list_commits_item(sha="b" * 40)

    event_a = commit_to_event(commit_a, github_repo_id=11, repository_id=1)
    event_b = commit_to_event(commit_b, github_repo_id=22, repository_id=1)

    assert event_a.external_key == f"commit:11:{'a' * 40}"
    assert event_b.external_key == f"commit:22:{'b' * 40}"
    assert event_a.external_key != event_b.external_key
    assert event_a.repository_id == event_b.repository_id == 1


def test_commit_to_event_keeps_bot_login_verbatim() -> None:
    commit = _github_list_commits_item(
        author={"login": "dependabot[bot]", "id": 49699333, "type": "Bot"},
    )

    event = commit_to_event(commit, github_repo_id=_GITHUB_REPO_ID, repository_id=1)

    assert event.author_login == "dependabot[bot]"


@pytest.mark.parametrize(
    "message",
    [
        "",
        "Fix all the bugs",
        "subject\n\nbody line 1\nbody line 2",
    ],
)
def test_commit_to_event_preserves_commit_message_exactly(message: str) -> None:
    commit = _github_list_commits_item(message=message)

    event = commit_to_event(commit, github_repo_id=_GITHUB_REPO_ID, repository_id=1)

    assert event.message == message
    assert event.message is not None


def test_commit_to_event_parses_github_zulu_timestamp() -> None:
    """GitHub documents timestamps as YYYY-MM-DDTHH:MM:SSZ."""
    commit = _github_list_commits_item(author_date="2024-06-02T08:05:09Z")

    event = commit_to_event(commit, github_repo_id=_GITHUB_REPO_ID, repository_id=1)

    assert event.occurred_at == datetime(2024, 6, 2, 8, 5, 9, tzinfo=timezone.utc)
    assert event.occurred_at.tzinfo is timezone.utc
