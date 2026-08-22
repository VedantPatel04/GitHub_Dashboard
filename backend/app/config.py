from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    app_env: str = "local"
    github_client_id: str
    github_client_secret: str
    github_oauth_redirect_uri: str
    github_allowed_login: str
    github_repos: str
    session_secret: str
    frontend_origin: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def github_repo_list(self) -> list[str]: # this is temporary for preset list of repos the API has access to
        repos: list[str] = []
        for raw in self.github_repos.split(","):
            repo = raw.strip()
            if not repo:
                continue
            parts = repo.split("/")
            if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
                raise ValueError(
                    f"Invalid GitHub repo {repo!r}; expected owner/name"
                )
            repos.append(f"{parts[0].strip()}/{parts[1].strip()}")
        if not repos:
            raise ValueError(
                "GITHUB_REPOS must list at least one owner/name repository"
            )
        return repos


@lru_cache
def get_settings() -> Settings: #cached so the .env file is only read once, not on every start
    settings = Settings()
    settings.github_repo_list()
    return settings
