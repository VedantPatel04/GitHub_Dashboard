from pydantic import BaseModel

class Dashboard(BaseModel):
    commit_count: int
    pr_opened_count: int
    pr_merged_count: int
    active_repo_count: int
    