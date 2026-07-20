from fastapi import APIRouter

from app.api.v1.alerts import router as alerts_router
from app.api.v1.auth import router as auth_router
from app.api.v1.events import router as events_router
from app.api.v1.patients import router as patients_router
from app.api.v1.reports import router as reports_router
from app.api.v1.rules import router as rules_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="", tags=["auth"])
api_router.include_router(events_router, prefix="", tags=["events"])
api_router.include_router(patients_router, prefix="", tags=["patients"])
api_router.include_router(alerts_router, prefix="", tags=["alerts"])
api_router.include_router(reports_router, prefix="", tags=["reports"])
api_router.include_router(rules_router, prefix="", tags=["rules"])
