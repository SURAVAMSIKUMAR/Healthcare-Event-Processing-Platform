import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.security import User, UserRole
from app.services.auth import hash_password, seed_admin_user
from app.services.rule_engine import seed_default_rules

settings = get_settings()


async def ensure_user(
    username: str,
    password: str,
    role: UserRole,
    hospital: str | None,
    department: str | None,
) -> None:
    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.username == username))
        existing = result.scalar_one_or_none()
        if existing is not None:
            return

        session.add(
            User(
                username=username,
                password_hash=hash_password(password),
                role=role,
                hospital=hospital,
                department=department,
            )
        )
        await session.commit()


async def seed() -> None:
    async with SessionLocal() as session:
        await seed_default_rules(session)
        await seed_admin_user(session)

    if settings.demo_hospital_user_password:
        await ensure_user(
            username="hospital_user",
            password=settings.demo_hospital_user_password,
            role=UserRole.HOSPITAL_USER,
            hospital="General Hospital",
            department="ICU",
        )
    if settings.demo_clinician_user_password:
        await ensure_user(
            username="clinician_user",
            password=settings.demo_clinician_user_password,
            role=UserRole.CLINICIAN,
            hospital="General Hospital",
            department="Cardiology",
        )
    if settings.demo_auditor_user_password:
        await ensure_user(
            username="auditor_user",
            password=settings.demo_auditor_user_password,
            role=UserRole.AUDITOR,
            hospital="General Hospital",
            department="Quality",
        )


if __name__ == "__main__":
    asyncio.run(seed())
