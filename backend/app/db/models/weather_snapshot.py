from sqlalchemy import Column, Integer, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from app.db.base import Base, created_at
from sqlalchemy.sql import func

class WeatherSnapshot(Base):
    __tablename__ = "weather_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    segment_id = Column(Integer, ForeignKey("road_segments.id"), nullable=True)
    geom = Column(Geometry(geometry_type='POINT', srid=4326, spatial_index=True), nullable=False)
    rainfall = Column(Float, nullable=False)  # mm
    temperature = Column(Float, nullable=False)  # celsius
    wind_speed = Column(Float, nullable=False)  # km/h
    humidity = Column(Float, nullable=False)  # percentage
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Inherited columns: created_at

    # Relationships
    segment = relationship("RoadSegment")

    def __repr__(self):
        return f"<WeatherSnapshot id={self.id} rainfall={self.rainfall}mm>"