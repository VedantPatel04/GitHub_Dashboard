from fastapi import APIRouter
from fastapi import Request
from fastapi.responses import RedirectResponse

from app.config import get_settings

import secrets
from urllib.parse import urlencode


router = APIRouter(prefix="/api/auth")

@router.get("/github",):
def async github_auth(request: Request):
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state

    url = "https://github.com/login/oauth/authorize" + urlencode({
        "client_id": get_settings().github_client_id,
        "redirect_uri": get_settings().github_oauth_redirect_uri,
        "state": state,
        "scope": "read:user",
    })
    return RedirectResponse(url)