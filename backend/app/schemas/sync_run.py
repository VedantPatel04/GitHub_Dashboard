from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SyncRunPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None
