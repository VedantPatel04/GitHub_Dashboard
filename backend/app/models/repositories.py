from app.db.session import Base
from sqlalchemy.orm import Mapped, mapped_column


class Repository(Base):
    __tablename__ = "repositories"
    id: Mapped[int] = mapped_column(primary_key=True)
    github_id: Mapped[int] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column()
    owner_login: Mapped[str] = mapped_column()
    full_name: Mapped[str] = mapped_column()
    private: Mapped[bool] = mapped_column()
    html_url: Mapped[str] = mapped_column()
    default_branch: Mapped[str] = mapped_column()