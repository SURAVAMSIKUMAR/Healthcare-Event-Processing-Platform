import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AdmissionRecordStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DISCHARGED = "DISCHARGED"


class ProcessingHistoryStatus(str, enum.Enum):
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class Patient(Base):
    __tablename__ = "patients"

    patient_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    hospital: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    department: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Admission(Base):
    __tablename__ = "admissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    admission_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patients.patient_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hospital: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    department: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[AdmissionRecordStatus] = mapped_column(
        Enum(AdmissionRecordStatus, name="admission_record_status"),
        nullable=False,
        default=AdmissionRecordStatus.ACTIVE,
        index=True,
    )
    admitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    discharged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_admissions_patient_admitted", "patient_id", "admitted_at"),
    )


class Observation(Base):
    __tablename__ = "observations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False, index=True
    )
    heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    systolic_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    diastolic_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    temperature_c: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    respiratory_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    oxygen_saturation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_observations_patient_observed", "patient_id", "observed_at"),
    )


class LabResultRecord(Base):
    __tablename__ = "lab_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False, index=True
    )
    test_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(128), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    reference_range: Mapped[str] = mapped_column(String(64), nullable=False)
    abnormal_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_lab_results_patient_observed", "patient_id", "observed_at"),
    )


class MedicationOrderRecord(Base):
    __tablename__ = "medication_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False, index=True
    )
    medication_name: Mapped[str] = mapped_column(String(128), nullable=False)
    dose: Mapped[str] = mapped_column(String(64), nullable=False)
    route: Mapped[str] = mapped_column(String(64), nullable=False)
    frequency: Mapped[str] = mapped_column(String(64), nullable=False)
    ordered_by: Mapped[str] = mapped_column(String(128), nullable=False)
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_medication_orders_patient_ordered", "patient_id", "ordered_at"),
    )


class ProcessingHistory(Base):
    __tablename__ = "processing_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    patient_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[ProcessingHistoryStatus] = mapped_column(
        Enum(ProcessingHistoryStatus, name="processing_history_status"),
        nullable=False,
        index=True,
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processor: Mapped[str] = mapped_column(String(128), nullable=False, default="celery_worker")
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class HospitalSummaryDaily(Base):
    __tablename__ = "hospital_summary_daily"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    summary_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    hospital: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    department: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active_patient_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    critical_alert_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_processing_time_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("summary_date", "hospital", "department", name="uq_summary_day_hosp_dept"),
        Index("ix_summary_day_hosp_dept", "summary_date", "hospital", "department"),
    )
