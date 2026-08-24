from app.db.session import Base
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime


class SyncRun(Base):
    __tablename__ = "sync_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column()
    started_at: Mapped[datetime] = mapped_column()
    finished_at: Mapped[datetime|None] = mapped_column()
    error_message: Mapped[str|None] = mapped_column()