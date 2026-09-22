"""SQLAlchemy ORM model for access's table (DOC 3 LC-10: access owns users)."""

from __future__ import annotations

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from nakabandi.shared import Base


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("name", name="uq_users_name"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    scope_state_id: Mapped[str | None] = mapped_column(String, nullable=True)
    scope_district_id: Mapped[str | None] = mapped_column(String, nullable=True)
    scope_bank_id: Mapped[str | None] = mapped_column(String, nullable=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    locale: Mapped[str] = mapped_column(String, nullable=False, default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
