from sqlalchemy import Column, Integer, String, Text, Float, DateTime, CheckConstraint
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from app.db.base import Base, created_at
from sqlalchemy.sql import func

class LandslideEvent(Base):
    __tablename__ = "landslide_events"

    id = Column(Integer, primary_key=True, index=True)
    landslide_category = Column(String(50), nullable=False)  # e.g., DEBRIS_FLOW, ROCK_FALL, SLUMP, EARTH_SLIDE, ROCK_SLIDE
    landslide_trigger = Column(String(50), nullable=False)  # e.g., RAINFALL, EARTHQUAKE, HUMAN_ACTIVITY
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    fatalities = Column(Integer, nullable=True)
    injuries = Column(Integer, nullable=True)
    date = Column(DateTime(timezone=True), nullable=True)
    location_details = Column(Text, nullable=True)
    geom = Column(Geometry(geometry_type='POINT', srid=4326, spatial_index=True), nullable=False)
    # Inherited columns: created_at

    def __repr__(self):
        return f"<LandslideEvent id={self.id} category={self.landslide_category} trigger={self.landslide_trigger}>"
