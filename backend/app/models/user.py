from app.db.session import Base
from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column



class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    github_id: Mapped[int] = mapped_column(unique=True)
    login: Mapped[str] = mapped_column(unique=True)
    avatar_url: Mapped[str] = mapped_column()
    access_token: Mapped[str] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now)