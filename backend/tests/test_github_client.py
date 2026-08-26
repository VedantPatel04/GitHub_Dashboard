from unittest.mock import MagicMock, patch

import httpx

from app.services.github_client import (
    GITHUB_API,
    _next_page_url,
    get_authenticated_user,
    get_repository,
    list_commits,
)


def test_next_page_url_extracts_next() -> None:
    header = (
        '<https://api.github.com/repos/o/n/commits?page=2>; rel="next", '
        '<https://api.github.com/repos/o/n/commits?page=8>; rel="last"'
    )
    assert (
        _next_page_url(header)
        == "https://api.github.com/repos/o/n/commits?page=2"
    )


def test_next_page_url_missing_or_no_next() -> None:
    assert _next_page_url(None) is None
    assert _next_page_url('<https://api.github.com/x>; rel="last"') is None


def _ok_response(payload: object, link: str | None = None) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    response.headers = {"Link": link} if link else {}
    response.raise_for_status.return_value = None
    return response


def _patch_client(mock_get: MagicMock):
    mock_client = MagicMock()
    mock_client.get = mock_get
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_client
    mock_cm.__exit__.return_value = False
    return patch(
        "app.services.github_client.httpx.Client",
        return_value=mock_cm,
    )


def test_get_authenticated_user_returns_json() -> None:
    mock_get = MagicMock(return_value=_ok_response({"login": "alice", "id": 1}))
    with _patch_client(mock_get):
        profile = get_authenticated_user("fake-token")
    assert profile["login"] == "alice"
    url = mock_get.call_args.args[0]
    assert url.endswith("/user")


def test_get_repository_hits_owner_name_path() -> None:
    payload = {"id": 99, "default_branch": "main", "full_name": "o/n"}
    mock_get = MagicMock(return_value=_ok_response(payload))
    with _patch_client(mock_get):
        repo = get_repository("fake-token", "o", "n")
    assert repo["id"] == 99
    assert mock_get.call_args.args[0] == f"{GITHUB_API}/repos/o/n"


def test_list_commits_sends_params_only_on_first_page() -> None:
    next_url = f"{GITHUB_API}/repos/o/n/commits?per_page=100&sha=main&page=2"
    page1 = _ok_response(
        [{"sha": "aaa"}],
        link=f'<{next_url}>; rel="next"',
    )
    page2 = _ok_response([{"sha": "bbb"}])
    mock_get = MagicMock(side_effect=[page1, page2])

    with _patch_client(mock_get):
        commits = list_commits(
            "fake-token", "o", "n", sha="main", max_pages=10
        )

    assert [c["sha"] for c in commits] == ["aaa", "bbb"]
    assert mock_get.call_count == 2

    first = mock_get.call_args_list[0]
    assert first.args[0] == f"{GITHUB_API}/repos/o/n/commits"
    assert first.kwargs["params"] == {"per_page": 100, "sha": "main"}

    second = mock_get.call_args_list[1]
    assert second.args[0] == next_url
    assert second.kwargs["params"] is None


def test_list_commits_stops_when_link_has_no_next() -> None:
    mock_get = MagicMock(return_value=_ok_response([{"sha": "only"}]))
    with _patch_client(mock_get):
        commits = list_commits("fake-token", "o", "n", max_pages=10)
    assert len(commits) == 1
    assert mock_get.call_count == 1


def test_list_commits_respects_max_pages() -> None:
    next_url = f"{GITHUB_API}/repos/o/n/commits?page=2"
    looping = _ok_response(
        [{"sha": "a"}],
        link=f'<{next_url}>; rel="next"',
    )
    mock_get = MagicMock(return_value=looping)
    with _patch_client(mock_get):
        list_commits("fake-token", "o", "n", max_pages=3)
    assert mock_get.call_count == 3


def test_get_repository_raises_on_http_error() -> None:
    response = MagicMock()
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "fail",
        request=MagicMock(),
        response=MagicMock(status_code=404),
    )
    mock_get = MagicMock(return_value=response)
    with _patch_client(mock_get):
        try:
            get_repository("fake-token", "o", "missing")
        except httpx.HTTPStatusError:
            return
        raise AssertionError("expected HTTPStatusError")
