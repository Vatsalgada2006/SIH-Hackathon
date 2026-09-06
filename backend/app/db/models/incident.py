from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, CheckConstraint
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from app.db.base import Base, created_at, updated_at
from sqlalchemy.sql import func
from enum import Enum

class IncidentStatus(str, Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"

class IncidentType(str, Enum):
    LANDSLIDE = "LANDSLIDE"
    FLOOD = "FLOOD"
    ACCIDENT = "ACCIDENT"
    CONSTRUCTION = "CONSTRUCTION"
    OTHER = "OTHER"

class IncidentSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    description = Column(Text, nullable=False)
    incident_type = Column(String(50), nullable=False)  # e.g., LANDSLIDE, FLOOD, ACCIDENT, CONSTRUCTION
    severity = Column(String(20), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    geom = Column(Geometry(geometry_type='POINT', srid=4326, spatial_index=True), nullable=False)
    reported_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), nullable=False, server_default="PENDING")  # PENDING, VERIFIED, RESOLVED, REJECTED
    segment_id = Column(Integer, ForeignKey("road_segments.id"), nullable=True)  # Nearest road segment
    passable_for = Column(String(50), nullable=True)
    estimated_clearance_time_hrs = Column(Integer, nullable=True)
    delay_penalty_minutes = Column(Integer, nullable=True)
    reporting_agency = Column(String(100), nullable=True)
    # Inherited columns: created_at, updated_at

    # Relationships
    reporter = relationship("User", foreign_keys=[reporter_id])
    verifier = relationship("User", foreign_keys=[verified_by])
    segment = relationship("RoadSegment")

    # Check constraints
    __table_args__ = (
        CheckConstraint(incident_type.in_([e.value for e in IncidentType]), name='valid_incident_type'),
        CheckConstraint(severity.in_([e.value for e in IncidentSeverity]), name='valid_severity'),
        CheckConstraint(status.in_([e.value for e in IncidentStatus]), name='valid_incident_status'),
    )

    def __repr__(self):
        return f"<Incident id={self.id} type={self.incident_type} status={self.status}>"
