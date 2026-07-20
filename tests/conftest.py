from collections.abc import AsyncGenerator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db_session
from app.main import app
from app.models.security import User, UserRole
from app.services.auth import get_current_user


class DummyAsyncTx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalar_one(self):
        return self._value

    def all(self):
        return self._value

    def scalars(self):
        return SimpleNamespace(all=lambda: self._value)


class FakeSession:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.added = []

    async def execute(self, *args, **kwargs):
        if self.responses:
            return self.responses.pop(0)
        return FakeScalarResult(None)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        return None

    async def commit(self):
        return None

    async def rollback(self):
        return None

    async def refresh(self, _):
        return None

    def begin(self):
        return DummyAsyncTx()


@pytest.fixture
def admin_user() -> User:
    return User(
        id=1,
        username="admin",
        password_hash="x",
        role=UserRole.ADMIN,
        hospital=None,
        department=None,
    )


@pytest.fixture
def scoped_user() -> User:
    return User(
        id=2,
        username="hospital-user",
        password_hash="x",
        role=UserRole.HOSPITAL_USER,
        hospital="General Hospital",
        department="ICU",
    )


@pytest.fixture
def auditor_user() -> User:
    return User(
        id=3,
        username="auditor",
        password_hash="x",
        role=UserRole.AUDITOR,
        hospital="General Hospital",
        department="Quality",
    )


@pytest.fixture
def client_with_overrides(admin_user: User):
    session = FakeSession()

    async def _db_dep() -> AsyncGenerator[FakeSession, None]:
        yield session

    async def _user_dep() -> User:
        return admin_user

    app.dependency_overrides[get_db_session] = _db_dep
    app.dependency_overrides[get_current_user] = _user_dep

    with TestClient(app) as client:
        yield client, session

    app.dependency_overrides.clear()
