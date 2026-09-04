from sqlalchemy import Column, Integer, Float, String, ForeignKey, CheckConstraint, Boolean, Text, DateTime
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from app.db.base import Base, created_at, updated_at

class RoadSegment(Base):
    __tablename__ = "road_segments"

    id = Column(Integer, primary_key=True, index=True)
    start_node_id = Column(Integer, ForeignKey("road_nodes.id"), nullable=False)
    end_node_id = Column(Integer, ForeignKey("road_nodes.id"), nullable=False)
    geom = Column(Geometry(geometry_type='LINESTRING', srid=4326, spatial_index=True), nullable=False)
    length = Column(Float, nullable=True)
    name = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, server_default="UNKNOWN")  # OPEN, DEGRADED, BLOCKED, UNKNOWN
    # Manual override fields
    manual_override = Column(Boolean, nullable=False, server_default='false')
    manual_override_reason = Column(Text, nullable=True)
    override_timestamp = Column(DateTime(timezone=True), nullable=True)
    override_user_id = Column(Integer, nullable=True)
    # Inherited columns: created_at, updated_at

    # Relationships
    start_node = relationship("RoadNode", foreign_keys=[start_node_id])
    end_node = relationship("RoadNode", foreign_keys=[end_node_id])

    # Check constraint for status
    __table_args__ = (
        CheckConstraint(status.in_(['OPEN', 'DEGRADED', 'BLOCKED', 'UNKNOWN']), name='valid_segment_status'),
    )

    def __repr__(self):
        return f"<RoadSegment id={self.id} status={self.status} manual_override={self.manual_override}>"