from pydantic import BaseModel
from typing import Optional

class SegmentBase(BaseModel):
    id: int
    start_node_id: int
    end_node_id: int
    length: Optional[float] = None
    name: Optional[str] = None
    status: str

class SegmentResponse(SegmentBase):
    geojson: str  # GeoJSON representation of the geometry

    class Config:
        orm_mode = True

class SegmentStatusUpdate(BaseModel):
    status: str
    reason: Optional[str] = None

    @classmethod
    def __get_validators__(cls):
        # Alternatively, we can use a validator for the status field
        pass

    # We'll add a validator to ensure the status is one of the allowed values
    @staticmethod
    def validate_status(value: str):
        allowed = ['OPEN', 'DEGRADED', 'BLOCKED', 'UNKNOWN']
        if value not in allowed:
            raise ValueError(f"Status must be one of {allowed}")
        return value

    # Pydantic v2 way: use field validator
    # But we are using Pydantic v2? The project uses pydantic-settings, so likely v2.
    # We'll use a validator for the status field.
