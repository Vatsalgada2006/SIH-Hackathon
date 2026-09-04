from sqlalchemy import Column, Integer, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from app.db.base import Base, created_at
from sqlalchemy.sql import func

class VehiclePosition(Base):
    __tablename__ = "vehicle_positions"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    geom = Column(Geometry(geometry_type='POINT', srid=4326, spatial_index=True), nullable=False)
    speed = Column(Float, nullable=False)  # km/h
    direction = Column(Float, nullable=False)  # degrees
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Inherited columns: created_at

    # Relationships
    vehicle = relationship("Vehicle")

    def __repr__(self):
        return f"<VehiclePosition id={self.id} vehicle_id={self.vehicle_id} speed={self.speed}km/h>"