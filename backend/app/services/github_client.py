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
    if not link_header:
        return None
    for part in link_header.split(","):
        if 'rel="next"' not in part:
            continue
        start = part.find("<")
        end = part.find(">", start)
        if start != -1 and end != -1:
            return part[start + 1 : end]
    return None


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
    with httpx.Client() as client:
        response = client.get(
            f"{GITHUB_API}/repos/{owner}/{name}",
            headers=_headers(token),
        )
        response.raise_for_status()
        return response.json()

def list_commits(
    token: str,
    owner: str,
    name: str,
    *,
    sha: str | None = None,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> list[dict[str, Any]]:
    """GET /repos/{owner}/{name}/commits, following Link rel=next up to max_pages."""
    url: str | None = f"{GITHUB_API}/repos/{owner}/{name}/commits"
    params: dict[str, Any] | None = {"per_page": 100}
    if sha:
        params["sha"] = sha

    commits: list[dict[str, Any]] = []
    with httpx.Client() as client:
        for _ in range(max_pages):
            if url is None:
                break
            response = client.get(url, headers=_headers(token), params=params)
            response.raise_for_status()
            page = response.json()
            if isinstance(page, list):
                commits.extend(page)
            url = _next_page_url(response.headers.get("Link")) # retrieves link header (returned with response.json()) 
            params = None                                    # which contains next page and last page URL's in <"string"> format + comma separated
    return commits
