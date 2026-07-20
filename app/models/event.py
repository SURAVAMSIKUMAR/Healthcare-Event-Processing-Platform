import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Index, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EventType(str, enum.Enum):
    VITALS = "VITALS"
    LAB_RESULT = "LAB_RESULT"
    MEDICATION_ORDER = "MEDICATION_ORDER"
    PATIENT_ADMISSION = "PATIENT_ADMISSION"
    PATIENT_DISCHARGE = "PATIENT_DISCHARGE"


class IngestionStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    ENQUEUED = "ENQUEUED"
    FAILED = "FAILED"


class RawEvent(Base):
    __tablename__ = "raw_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType, name="event_type"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[IngestionStatus] = mapped_column(
        Enum(IngestionStatus, name="ingestion_status"),
        default=IngestionStatus.RECEIVED,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_raw_events_patient_time", "patient_id", "occurred_at"),
    )
