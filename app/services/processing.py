from datetime import UTC, datetime
import time

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinical import (
    Admission,
    AdmissionRecordStatus,
    HospitalSummaryDaily,
    LabResultRecord,
    MedicationOrderRecord,
    Observation,
    Patient,
    ProcessingHistory,
    ProcessingHistoryStatus,
)
from app.models.event import EventType, IngestionStatus, RawEvent
from app.models.processing import (
    AdmissionStatus,
    Alert,
    AlertSeverity,
    AlertStatus,
    FailedEvent,
    PatientState,
    ProcessedEvent,
)
from app.services.rule_engine import build_alerts_for_event


class TransientProcessingError(Exception):
    pass


class PermanentProcessingError(Exception):
    pass


def get_summary_dimensions(raw_event: RawEvent, normalized: dict) -> tuple[str, str]:
    if raw_event.event_type == EventType.PATIENT_ADMISSION:
        hospital = str(normalized.get("facility") or "UNKNOWN")
        department = str(normalized.get("department") or "UNKNOWN")
        return hospital, department
    return "UNKNOWN", "UNKNOWN"


async def resolve_summary_dimensions(
    session: AsyncSession,
    raw_event: RawEvent,
    normalized: dict,
) -> tuple[str, str]:
    result = await session.execute(select(Patient).where(Patient.patient_id == raw_event.patient_id))
    patient = result.scalar_one_or_none()
    if patient is not None and patient.hospital and patient.department:
        return patient.hospital, patient.department
    return get_summary_dimensions(raw_event, normalized)


def normalize_event_payload(event: RawEvent) -> dict:
    payload = event.payload
    if not isinstance(payload, dict):
        raise PermanentProcessingError("Payload must be a JSON object.")

    normalized = dict(payload)
    normalized["event_id"] = event.event_id
    normalized["event_type"] = event.event_type.value
    normalized["patient_id"] = event.patient_id
    normalized["occurred_at"] = event.occurred_at.isoformat()

    # Force booleans to numeric where rules are numeric-based (e.g., abnormal_flag EQ 1).
    if "abnormal_flag" in normalized:
        normalized["abnormal_flag"] = 1.0 if bool(normalized["abnormal_flag"]) else 0.0

    return normalized


def should_apply_event_to_state(
    latest_event_timestamp: datetime | None,
    incoming_event_timestamp: datetime,
) -> bool:
    if latest_event_timestamp is None:
        return True
    return incoming_event_timestamp >= latest_event_timestamp


def extract_latest_clinical_values(raw_event: RawEvent, normalized: dict) -> dict:
    values: dict = {}
    if raw_event.event_type == EventType.VITALS:
        for key in [
            "heart_rate",
            "systolic_bp",
            "diastolic_bp",
            "temperature_c",
            "respiratory_rate",
            "oxygen_saturation",
        ]:
            if key in normalized:
                values[key] = normalized[key]
    elif raw_event.event_type == EventType.LAB_RESULT:
        for key in ["test_name", "value", "unit", "reference_range", "abnormal_flag"]:
            if key in normalized:
                values[key] = normalized[key]
    return values


async def get_or_lock_patient_state(session: AsyncSession, patient_id: str) -> PatientState:
    # Ensure row exists, then lock the row in the transaction for safe concurrent updates.
    stmt = insert(PatientState).values(
        patient_id=patient_id,
        admission_status=AdmissionStatus.UNKNOWN,
        latest_clinical_values={},
        active_critical_alert_count=0,
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=[PatientState.patient_id])
    await session.execute(stmt)

    result = await session.execute(
        select(PatientState)
        .where(PatientState.patient_id == patient_id)
        .with_for_update()
    )
    patient_state = result.scalar_one_or_none()
    if patient_state is None:
        raise PermanentProcessingError(f"Patient state missing for patient_id={patient_id}")
    return patient_state


async def count_active_critical_alerts(session: AsyncSession, patient_id: str) -> int:
    result = await session.execute(
        select(func.count(Alert.id)).where(
            Alert.patient_id == patient_id,
            Alert.severity == AlertSeverity.CRITICAL,
            Alert.status == AlertStatus.OPEN,
        )
    )
    return int(result.scalar_one())


async def apply_patient_state_update(
    session: AsyncSession,
    raw_event: RawEvent,
    normalized: dict,
) -> str:
    patient_state = await get_or_lock_patient_state(session, raw_event.patient_id)
    if not should_apply_event_to_state(patient_state.latest_event_timestamp, raw_event.occurred_at):
        patient_state.active_critical_alert_count = await count_active_critical_alerts(
            session, raw_event.patient_id
        )
        return "stale_event_ignored_for_state"

    patient_state.latest_event_timestamp = raw_event.occurred_at

    if raw_event.event_type == EventType.PATIENT_ADMISSION:
        patient_state.admission_status = AdmissionStatus.ADMITTED
        patient_state.hospital = str(normalized.get("facility") or patient_state.hospital or "") or None
        patient_state.department = (
            str(normalized.get("department") or patient_state.department or "") or None
        )
    elif raw_event.event_type == EventType.PATIENT_DISCHARGE:
        patient_state.admission_status = AdmissionStatus.DISCHARGED

    latest_values = dict(patient_state.latest_clinical_values or {})
    latest_values.update(extract_latest_clinical_values(raw_event, normalized))
    patient_state.latest_clinical_values = latest_values
    patient_state.active_critical_alert_count = await count_active_critical_alerts(
        session, raw_event.patient_id
    )
    return "state_updated"


async def upsert_patient_record(
    session: AsyncSession,
    raw_event: RawEvent,
    normalized: dict,
) -> None:
    stmt = insert(Patient).values(
        patient_id=raw_event.patient_id,
        hospital=str(normalized.get("facility") or "") or None,
        department=str(normalized.get("department") or "") or None,
        is_active=True,
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=[Patient.patient_id])
    await session.execute(stmt)

    result = await session.execute(select(Patient).where(Patient.patient_id == raw_event.patient_id))
    patient = result.scalar_one()
    if raw_event.event_type == EventType.PATIENT_ADMISSION:
        patient.hospital = str(normalized.get("facility") or patient.hospital or "") or None
        patient.department = str(normalized.get("department") or patient.department or "") or None
        patient.is_active = True
    elif raw_event.event_type == EventType.PATIENT_DISCHARGE:
        patient.is_active = False


async def persist_domain_record(session: AsyncSession, raw_event: RawEvent, normalized: dict) -> None:
    if raw_event.event_type == EventType.VITALS:
        session.add(
            Observation(
                event_id=raw_event.event_id,
                patient_id=raw_event.patient_id,
                heart_rate=normalized.get("heart_rate"),
                systolic_bp=normalized.get("systolic_bp"),
                diastolic_bp=normalized.get("diastolic_bp"),
                temperature_c=normalized.get("temperature_c"),
                respiratory_rate=normalized.get("respiratory_rate"),
                oxygen_saturation=normalized.get("oxygen_saturation"),
                observed_at=raw_event.occurred_at,
            )
        )
    elif raw_event.event_type == EventType.LAB_RESULT:
        session.add(
            LabResultRecord(
                event_id=raw_event.event_id,
                patient_id=raw_event.patient_id,
                test_name=str(normalized.get("test_name") or ""),
                value=str(normalized.get("value") or ""),
                unit=str(normalized.get("unit") or ""),
                reference_range=str(normalized.get("reference_range") or ""),
                abnormal_flag=bool(normalized.get("abnormal_flag") == 1.0),
                observed_at=raw_event.occurred_at,
            )
        )
    elif raw_event.event_type == EventType.MEDICATION_ORDER:
        session.add(
            MedicationOrderRecord(
                event_id=raw_event.event_id,
                patient_id=raw_event.patient_id,
                medication_name=str(normalized.get("medication_name") or ""),
                dose=str(normalized.get("dose") or ""),
                route=str(normalized.get("route") or ""),
                frequency=str(normalized.get("frequency") or ""),
                ordered_by=str(normalized.get("ordered_by") or ""),
                ordered_at=raw_event.occurred_at,
            )
        )
    elif raw_event.event_type == EventType.PATIENT_ADMISSION:
        session.add(
            Admission(
                admission_id=str(normalized.get("admission_id") or "unknown-admission"),
                patient_id=raw_event.patient_id,
                hospital=str(normalized.get("facility") or "") or None,
                department=str(normalized.get("department") or "") or None,
                status=AdmissionRecordStatus.ACTIVE,
                admitted_at=raw_event.occurred_at,
            )
        )
    elif raw_event.event_type == EventType.PATIENT_DISCHARGE:
        admission_id = str(normalized.get("admission_id") or "")
        if admission_id:
            result = await session.execute(
                select(Admission)
                .where(Admission.admission_id == admission_id, Admission.patient_id == raw_event.patient_id)
                .order_by(Admission.admitted_at.desc())
                .limit(1)
            )
            admission = result.scalar_one_or_none()
            if admission is not None:
                admission.status = AdmissionRecordStatus.DISCHARGED
                admission.discharged_at = raw_event.occurred_at


async def recompute_summary_point_metrics(session: AsyncSession, hospital: str, department: str) -> tuple[int, int]:
    active_patients_result = await session.execute(
        select(func.count(Patient.patient_id)).where(
            Patient.is_active.is_(True),
            Patient.hospital == hospital,
            Patient.department == department,
        )
    )
    critical_result = await session.execute(
        select(func.sum(PatientState.active_critical_alert_count)).where(
            PatientState.hospital == hospital,
            PatientState.department == department,
        )
    )
    return int(active_patients_result.scalar_one() or 0), int(critical_result.scalar_one() or 0)


async def upsert_summary_daily(
    session: AsyncSession,
    summary_date: datetime,
    hospital: str,
    department: str,
    event_delta: int,
    failure_delta: int,
    processing_time_ms_delta: int,
    processed_event_delta: int,
) -> None:
    stmt = insert(HospitalSummaryDaily).values(
        summary_date=summary_date,
        hospital=hospital,
        department=department,
        event_count=0,
        failure_count=0,
        active_patient_count=0,
        critical_alert_count=0,
        total_processing_time_ms=0,
        processed_event_count=0,
    )
    stmt = stmt.on_conflict_do_nothing(
        index_elements=[
            HospitalSummaryDaily.summary_date,
            HospitalSummaryDaily.hospital,
            HospitalSummaryDaily.department,
        ]
    )
    await session.execute(stmt)

    result = await session.execute(
        select(HospitalSummaryDaily)
        .where(
            HospitalSummaryDaily.summary_date == summary_date,
            HospitalSummaryDaily.hospital == hospital,
            HospitalSummaryDaily.department == department,
        )
        .with_for_update()
    )
    summary = result.scalar_one()

    summary.event_count += event_delta
    summary.failure_count += failure_delta
    summary.total_processing_time_ms += processing_time_ms_delta
    summary.processed_event_count += processed_event_delta

    active_patients, critical_alerts = await recompute_summary_point_metrics(
        session=session,
        hospital=hospital,
        department=department,
    )
    summary.active_patient_count = active_patients
    summary.critical_alert_count = critical_alerts


async def add_processing_history(
    session: AsyncSession,
    event_id: str,
    patient_id: str | None,
    status: ProcessingHistoryStatus,
    attempt: int,
    processing_time_ms: int | None,
    error_type: str | None,
    error_message: str | None,
    metadata_json: dict,
) -> None:
    session.add(
        ProcessingHistory(
            event_id=event_id,
            patient_id=patient_id,
            status=status,
            attempt=attempt,
            processing_time_ms=processing_time_ms,
            error_type=error_type,
            error_message=error_message,
            metadata_json=metadata_json,
        )
    )


async def process_event_by_id(
    session: AsyncSession,
    event_id: str,
    retry_count: int,
) -> dict[str, int | str]:
    started_at = time.perf_counter()
    async with session.begin():
        result = await session.execute(select(RawEvent).where(RawEvent.event_id == event_id))
        raw_event = result.scalar_one_or_none()
        if raw_event is None:
            raise PermanentProcessingError(f"Raw event not found for event_id={event_id}")

        await add_processing_history(
            session=session,
            event_id=event_id,
            patient_id=raw_event.patient_id,
            status=ProcessingHistoryStatus.STARTED,
            attempt=retry_count,
            processing_time_ms=None,
            error_type=None,
            error_message=None,
            metadata_json={"phase": "start"},
        )

        processed_exists = await session.execute(
            select(ProcessedEvent).where(ProcessedEvent.event_id == event_id)
        )
        if processed_exists.scalar_one_or_none() is not None:
            return {"event_id": event_id, "alerts_created": 0, "status": "already_processed"}

        normalized = normalize_event_payload(raw_event)
        await upsert_patient_record(session, raw_event, normalized)
        await persist_domain_record(session, raw_event, normalized)

        processed = ProcessedEvent(
            event_id=raw_event.event_id,
            raw_event_id=raw_event.id,
            patient_id=raw_event.patient_id,
            event_type=raw_event.event_type.value,
            occurred_at=raw_event.occurred_at,
            normalized_data=normalized,
        )
        session.add(processed)

        alerts = await build_alerts_for_event(session, raw_event, normalized)
        for alert in alerts:
            session.add(alert)

        await session.flush()
        state_result = await apply_patient_state_update(session, raw_event, normalized)

        processing_time_ms = int((time.perf_counter() - started_at) * 1000)
        hospital, department = await resolve_summary_dimensions(session, raw_event, normalized)
        summary_date = raw_event.occurred_at.replace(hour=0, minute=0, second=0, microsecond=0)
        await upsert_summary_daily(
            session=session,
            summary_date=summary_date,
            hospital=hospital,
            department=department,
            event_delta=1,
            failure_delta=0,
            processing_time_ms_delta=processing_time_ms,
            processed_event_delta=1,
        )

        await add_processing_history(
            session=session,
            event_id=event_id,
            patient_id=raw_event.patient_id,
            status=ProcessingHistoryStatus.SUCCESS,
            attempt=retry_count,
            processing_time_ms=processing_time_ms,
            error_type=None,
            error_message=None,
            metadata_json={"alerts_created": len(alerts), "state_result": state_result},
        )

        raw_event.status = IngestionStatus.ENQUEUED

    return {
        "event_id": event_id,
        "alerts_created": len(alerts),
        "status": f"processed:{state_result}",
    }


async def dead_letter_event(
    session: AsyncSession,
    event_id: str,
    reason: str,
    error_type: str,
    retry_count: int,
) -> None:
    async with session.begin():
        result = await session.execute(select(RawEvent).where(RawEvent.event_id == event_id))
        raw_event = result.scalar_one_or_none()
        if raw_event is None:
            return

        raw_event.status = IngestionStatus.FAILED
        failed = FailedEvent(
            event_id=event_id,
            raw_event_id=raw_event.id,
            reason=reason,
            error_type=error_type,
            retry_count=retry_count,
            dead_letter_payload=raw_event.payload,
            moved_to_dead_letter_at=datetime.now(UTC),
        )
        session.add(failed)

        normalized = normalize_event_payload(raw_event)
        hospital, department = await resolve_summary_dimensions(session, raw_event, normalized)
        summary_date = raw_event.occurred_at.replace(hour=0, minute=0, second=0, microsecond=0)
        await upsert_summary_daily(
            session=session,
            summary_date=summary_date,
            hospital=hospital,
            department=department,
            event_delta=0,
            failure_delta=1,
            processing_time_ms_delta=0,
            processed_event_delta=0,
        )
        await add_processing_history(
            session=session,
            event_id=event_id,
            patient_id=raw_event.patient_id,
            status=ProcessingHistoryStatus.FAILED,
            attempt=retry_count,
            processing_time_ms=None,
            error_type=error_type,
            error_message=reason,
            metadata_json={"phase": "dead_letter"},
        )
