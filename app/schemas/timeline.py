from datetime import datetime

from pydantic import BaseModel


class TimelineItem(BaseModel):
    event_id: str
    patient_id: str
    event_type: str
    occurred_at: datetime
    payload: dict
    processing_status: str


class TimelineResponse(BaseModel):
    items: list[TimelineItem]
    page: int
    page_size: int
    total: int
