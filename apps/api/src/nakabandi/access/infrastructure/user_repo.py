"""SqlUserRepo (DOC 3 M5)."""

from __future__ import annotations

from nakabandi_contracts.enums import Role
from sqlalchemy import select
from sqlalchemy.orm import Session

from nakabandi.access.domain.entities import User
from nakabandi.access.infrastructure.models import UserModel
from nakabandi.shared import Id


def _from_model(m: UserModel) -> User:
    return User(
        id=m.id,
        name=m.name,
        role=Role(m.role),
        scope_state_id=m.scope_state_id,
        scope_district_id=m.scope_district_id,
        scope_bank_id=m.scope_bank_id,
        password_hash=m.password_hash,
        locale=m.locale,
        is_active=m.is_active,
    )


class SqlUserRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_name(self, name: str) -> User | None:
        model = self._session.scalar(select(UserModel).where(UserModel.name == name))
        return _from_model(model) if model is not None else None

    def get_by_id(self, user_id: Id) -> User | None:
        model = self._session.get(UserModel, user_id)
        return _from_model(model) if model is not None else None

    def add(self, user: User) -> None:
        self._session.add(
            UserModel(
                id=user.id,
                name=user.name,
                role=user.role.value,
                scope_state_id=user.scope_state_id,
                scope_district_id=user.scope_district_id,
                scope_bank_id=user.scope_bank_id,
                password_hash=user.password_hash,
                locale=user.locale,
                is_active=user.is_active,
            )
        )
        self._session.flush()

    def list_all(self) -> list[User]:
        models = self._session.scalars(select(UserModel))
        return [_from_model(m) for m in models]
