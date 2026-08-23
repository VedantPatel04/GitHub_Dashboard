from app.db.session import Base
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from sqlalchemy import ForeignKey


class ActivityEvent(Base):
    __tablename__ = "activity_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    external_key: Mapped[str] = mapped_column(unique=True)
    event_type: Mapped[str] = mapped_column()
    html_url: Mapped[str | None] = mapped_column()
    occurred_at: Mapped[datetime] = mapped_column()
    author_login: Mapped[str|None] = mapped_column()
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"))
    message: Mapped[str|None] = mapped_column()