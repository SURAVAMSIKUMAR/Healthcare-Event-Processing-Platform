import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProcessingStatus(str, enum.Enum):
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class RuleOperator(str, enum.Enum):
    LT = "LT"
    LTE = "LTE"
    GT = "GT"
    GTE = "GTE"
    EQ = "EQ"
    BETWEEN = "BETWEEN"
    OUTSIDE_RANGE = "OUTSIDE_RANGE"


class AlertSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, enum.Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class AdmissionStatus(str, enum.Enum):
    UNKNOWN = "UNKNOWN"
    ADMITTED = "ADMITTED"
    DISCHARGED = "DISCHARGED"


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    raw_event_id: Mapped[int] = mapped_column(ForeignKey("raw_events.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    normalized_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status"),
        default=ProcessingStatus.PROCESSED,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FailedEvent(Base):
    __tablename__ = "failed_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    raw_event_id: Mapped[int] = mapped_column(ForeignKey("raw_events.id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    error_type: Mapped[str] = mapped_column(String(128), nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dead_letter_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    moved_to_dead_letter_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)
    operator: Mapped[RuleOperator] = mapped_column(Enum(RuleOperator, name="rule_operator"), nullable=False)
    value_num: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity, name="alert_severity"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    patient_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity, name="alert_severity_ref"), nullable=False
    )
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, name="alert_status"), nullable=False, default=AlertStatus.OPEN
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    acknowledgement_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_alerts_severity_status_time", "severity", "status", "triggered_at"),
    )


class PatientState(Base):
    __tablename__ = "patient_states"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    hospital: Mapped[str | None] = mapped_column(String(128), nullable=True)
    department: Mapped[str | None] = mapped_column(String(128), nullable=True)
    admission_status: Mapped[AdmissionStatus] = mapped_column(
        Enum(AdmissionStatus, name="admission_status"),
        nullable=False,
        default=AdmissionStatus.UNKNOWN,
    )
    latest_event_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latest_clinical_values: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    active_critical_alert_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_patient_states_hospital_department", "hospital", "department"),
    )
