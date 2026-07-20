from datetime import datetime

from pydantic import BaseModel, Field


class AlertOut(BaseModel):
    id: int
    event_id: str
    patient_id: str
    rule_code: str
    severity: str
    status: str
    message: str
    triggered_at: datetime
    acknowledged_at: datetime | None
    acknowledged_by: str | None
    acknowledgement_note: str | None
    hospital: str | None = None
    department: str | None = None


class AlertsListResponse(BaseModel):
    items: list[AlertOut]
    page: int
    page_size: int
    total: int


class AcknowledgeAlertRequest(BaseModel):
    user: str = Field(min_length=1, max_length=128)
    comments: str = Field(min_length=1, max_length=500)


class AcknowledgeAlertResponse(BaseModel):
    id: int
    status: str
    acknowledged_at: datetime
    acknowledged_by: str
    acknowledgement_note: str
