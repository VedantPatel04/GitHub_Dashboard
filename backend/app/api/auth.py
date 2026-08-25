from datetime import datetime

import httpx
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import User as UserPublic

router = APIRouter(prefix="/api/auth")


@router.get("/github")
async def github_auth(request: Request): # redirects to GitHub with state created and stored in session cookie
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state

    url = "https://github.com/login/oauth/authorize?" + urlencode({ # requests users GitHub identity with params as defined
        "client_id": get_settings().github_client_id,
        "redirect_uri": get_settings().github_oauth_redirect_uri,
        "state": state,
        "scope": "read:user",
    })
    return RedirectResponse(url)


@router.get("/github/callback")
async def github_callback( # redirects back to frontend with user info, access token and session state (stored in URL for match validation )
    request: Request,
    code: str,
    state: str,
    db: Session = Depends(get_db),
):
    expected_state = request.session.pop("oauth_state", None)
    if expected_state != state: #checks if state in session == state from GitHub returned url payload
        raise HTTPException(status_code=400, detail="Invalid state")

    settings = get_settings()

    async with httpx.AsyncClient() as client:
        try:
            token_response = await client.post( #post to the GitHub url to get the GH access token
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"}, #specifies what format GitHub should return the response in
                data={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "code": code,
                    "redirect_uri": settings.github_oauth_redirect_uri,
                },
            )
            token_response.raise_for_status()
            access_token = token_response.json().get("access_token")
            if not access_token:
                raise HTTPException(status_code=400, detail="Missing access token")

            user_response = await client.get( #get the user info from the GitHub api
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "github-dashboard",
                },
            )
            user_response.raise_for_status()
            profile = user_response.json()
        except httpx.HTTPStatusError:
            raise HTTPException(status_code=502, detail="GitHub request failed")

    github_id = profile["id"]
    github_login = profile["login"]
    avatar_url = profile["avatar_url"]

    # check if user is on the github_allowed_login list before upserting user to db
    if github_login.lower() != settings.github_allowed_login.lower():
        raise HTTPException(status_code=403, detail="Login not allowed")

    user = db.execute(
        select(User).where(User.github_id == github_id)
    ).scalar_one_or_none() # checks if user is already in the database

    if user is None:
        user = User(
            github_id=github_id,
            login=github_login,
            avatar_url=avatar_url,
            access_token=access_token,
            updated_at=datetime.now(),
        )
        db.add(user) #add new user if not in database
    else: #update existing user if already in database
        user.login = github_login
        user.avatar_url = avatar_url
        user.access_token = access_token
        user.updated_at = datetime.now()

    db.commit()
    db.refresh(user)

    request.session["user_id"] = user.id # cookie stores db primary key in session, NOT THE github_id we handled earlier
    return RedirectResponse(settings.frontend_origin)



@router.get("/me", response_model=UserPublic) #retrieves user data from session cookie stored in router function above
def get_session_me(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return user


@router.post("/logout", status_code=204)
def logout(request: Request): # posts logout request and clears session cookies
    request.session.clear()
    return Response(status_code=204)