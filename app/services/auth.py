from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.security import User, UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class AuthContext:
    def __init__(self, user: User):
        self.user = user


settings = get_settings()


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(*, subject: str, role: str, hospital: str | None, department: str | None) -> str:
    expires_delta = timedelta(minutes=settings.jwt_expire_minutes)
    expire = datetime.now(UTC) + expires_delta
    to_encode = {
        "sub": subject,
        "role": role,
        "hospital": hospital,
        "department": department,
        "exp": expire,
    }
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc

    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


def require_roles(*roles: UserRole):
    async def _dep(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user

    return _dep


def enforce_hospital_scope(request: Request, user: User, hospital: str | None) -> None:
    request.state.scope_hospital = hospital if user.role != UserRole.ADMIN else None


async def seed_admin_user(session: AsyncSession) -> None:
    if not settings.bootstrap_admin_password:
        return

    result = await session.execute(select(User).where(User.username == settings.bootstrap_admin_username))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return

    session.add(
        User(
            username=settings.bootstrap_admin_username,
            password_hash=hash_password(settings.bootstrap_admin_password),
            role=UserRole.ADMIN,
            hospital=None,
            department=None,
        )
    )
    await session.commit()
