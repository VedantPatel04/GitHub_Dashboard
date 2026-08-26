from typing import Any

import httpx

GITHUB_API = "https://api.github.com"
USER_AGENT = "github-dashboard"
DEFAULT_MAX_PAGES = 10


def _headers(token: str) -> dict[str, str]: #A shared header for all requests to eliminate redundancy
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
    }


def _next_page_url(link_header: str | None) -> str | None: #Another helper function
    """Return the URL for rel=next from a GitHub Link header, or None."""
    


def get_authenticated_user(token: str) -> dict[str, Any]:
    """GET /user"""
    with httpx.Client() as client:
        response = client.get(
            "https://api.github.com/user",
            headers=_headers(token),
        )
        response.raise_for_status()
        return response.json()


def get_repository(token: str, owner: str, name: str) -> dict[str, Any]:
    """GET /repos/{owner}/{name}"""
    """
    what do we need to do here?

    call GET repos/{owner}/{name} with username of repo owner == login(func parameter: owner) and repo name(func parameter: name)
    returns a whole lotta stuff, find at: https://docs.github.com/en/rest/repos/repos?apiVersion=2026-03-10#get-a-repository :)


    RETURN: map with (ID, default_branch, full_name == login/repo_name)
    """


def list_commits(
    token: str,
    owner: str,
    name: str,
    *,
    sha: str | None = None,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> list[dict[str, Any]]:
    """GET /repos/{owner}/{name}/commits, following Link rel=next up to max_pages."""
