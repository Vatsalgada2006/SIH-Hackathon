from sqlalchemy import Column, Integer, String, Float, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from app.db.base import Base, created_at, updated_at

class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(String(50), unique=True, nullable=False)  # e.g., license plate
    type = Column(String(20), nullable=False)  # TRUCK, VAN, CAR, etc.
    capacity = Column(Float, nullable=True)  # in tons
    current_segment_id = Column(Integer, ForeignKey("road_segments.id"), nullable=True)
    # Inherited columns: created_at, updated_at

    # Relationships
    current_segment = relationship("RoadSegment")

    # Check constraint for type
    __table_args__ = (
        CheckConstraint(type.in_(['TRUCK', 'VAN', 'CAR', 'MOTORCYCLE', 'BUS']), name='valid_vehicle_type'),
    )

    def __repr__(self):
        return f"<Vehicle id={self.id} vehicle_id='{self.vehicle_id}' type={self.type}>"