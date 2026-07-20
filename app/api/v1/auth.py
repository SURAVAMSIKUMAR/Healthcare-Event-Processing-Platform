from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.security import User, UserRole
from app.schemas.auth import LoginRequest, TokenResponse, UserCreateRequest, UserOut
from app.services.audit import write_audit_log
from app.services.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_roles,
    verify_password,
)

router = APIRouter()


@router.post("/auth/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(
    body: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    result = await session.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        await write_audit_log(
            session=session,
            request=request,
            action="LOGIN_ATTEMPT",
            resource_type="auth",
            resource_id=body.username,
            outcome="FAILURE",
            user=None,
            details={"reason": "invalid_credentials"},
        )
        await session.commit()
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token(
        subject=user.username,
        role=user.role.value,
        hospital=user.hospital,
        department=user.department,
    )
    await write_audit_log(
        session=session,
        request=request,
        action="LOGIN_ATTEMPT",
        resource_type="auth",
        resource_id=user.username,
        outcome="SUCCESS",
        user=user,
        details={"role": user.role.value},
    )
    await session.commit()

    return TokenResponse(
        access_token=token,
        role=user.role.value,
        hospital=user.hospital,
        department=user.department,
    )


@router.post(
    "/admin/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    body: UserCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> UserOut:
    try:
        role = UserRole(body.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid role") from exc

    existing = await session.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=role,
        hospital=body.hospital,
        department=body.department,
    )
    session.add(user)
    await write_audit_log(
        session=session,
        request=request,
        action="ADMIN_ACTION",
        resource_type="user",
        resource_id=body.username,
        outcome="SUCCESS",
        user=admin_user,
        details={"operation": "create_user", "role": role.value},
    )
    await session.commit()
    await session.refresh(user)

    return UserOut(
        id=user.id,
        username=user.username,
        role=user.role.value,
        hospital=user.hospital,
        department=user.department,
    )


@router.get("/auth/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role.value,
        hospital=current_user.hospital,
        department=current_user.department,
    )
