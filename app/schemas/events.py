from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class VitalsPayload(BaseModel):
    heart_rate: int = Field(ge=20, le=250)
    systolic_bp: int = Field(ge=60, le=300)
    diastolic_bp: int = Field(ge=30, le=200)
    temperature_c: float = Field(ge=30, le=45)
    respiratory_rate: int = Field(ge=5, le=80)
    oxygen_saturation: int = Field(ge=50, le=100)


class LabResultPayload(BaseModel):
    test_name: str = Field(min_length=1, max_length=128)
    value: str = Field(min_length=1, max_length=128)
    unit: str = Field(min_length=1, max_length=32)
    reference_range: str = Field(min_length=1, max_length=64)
    abnormal_flag: bool = False


class MedicationOrderPayload(BaseModel):
    medication_name: str = Field(min_length=1, max_length=128)
    dose: str = Field(min_length=1, max_length=64)
    route: str = Field(min_length=1, max_length=64)
    frequency: str = Field(min_length=1, max_length=64)
    ordered_by: str = Field(min_length=1, max_length=128)


class PatientAdmissionPayload(BaseModel):
    admission_id: str = Field(min_length=1, max_length=128)
    facility: str = Field(min_length=1, max_length=128)
    department: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=255)


class PatientDischargePayload(BaseModel):
    admission_id: str = Field(min_length=1, max_length=128)
    disposition: str = Field(min_length=1, max_length=128)
    summary: str = Field(min_length=1, max_length=500)
    follow_up_required: bool = False


class BaseEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=128)
    occurred_at: datetime
    patient_id: str = Field(min_length=1, max_length=128)


class VitalsEvent(BaseEvent):
    event_type: Literal["VITALS"]
    payload: VitalsPayload


class LabResultEvent(BaseEvent):
    event_type: Literal["LAB_RESULT"]
    payload: LabResultPayload


class MedicationOrderEvent(BaseEvent):
    event_type: Literal["MEDICATION_ORDER"]
    payload: MedicationOrderPayload


class PatientAdmissionEvent(BaseEvent):
    event_type: Literal["PATIENT_ADMISSION"]
    payload: PatientAdmissionPayload


class PatientDischargeEvent(BaseEvent):
    event_type: Literal["PATIENT_DISCHARGE"]
    payload: PatientDischargePayload


EventIn = Annotated[
    VitalsEvent
    | LabResultEvent
    | MedicationOrderEvent
    | PatientAdmissionEvent
    | PatientDischargeEvent,
    Field(discriminator="event_type"),
]


class EventIngestionResponse(BaseModel):
    event_id: str
    accepted: bool
    duplicate: bool
    status: str
    detail: str
