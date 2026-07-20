from pydantic import BaseModel


class HospitalSummaryItem(BaseModel):
    hospital: str
    department: str
    event_count: int
    failure_count: int
    active_patient_count: int
    critical_alert_count: int
    avg_processing_time_ms: float


class HospitalSummaryResponse(BaseModel):
    generated_rows: int
    grouped: list[HospitalSummaryItem]
