from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class IncidentBase(BaseModel):
    id: int
    reporter_id: Optional[int]
    description: str
    incident_type: str
    severity: str
    latitude: float
    longitude: float
    segment_id: Optional[int]
    reported_at: datetime
    verified_at: Optional[datetime]
    verified_by: Optional[int]
    resolved_at: Optional[datetime]
    status: str

class IncidentResponse(IncidentBase):
    geojson: str  # GeoJSON representation of the geometry

    class Config:
        orm_mode = True

class IncidentCreate(BaseModel):
    reporter_id: Optional[int]
    description: str
    incident_type: str
    severity: str
    latitude: float
    longitude: float
    segment_id: Optional[int] = None

class IncidentUpdate(BaseModel):
    reporter_id: Optional[int]
    description: Optional[str] = None
    incident_type: Optional[str] = None
    severity: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    segment_id: Optional[int] = None

class IncidentVerify(BaseModel):
    verified_by: int

class IncidentResolve(BaseModel):
    pass