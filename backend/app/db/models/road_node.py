from sqlalchemy import Column, Integer
from geoalchemy2 import Geometry
from app.db.base import Base, created_at

class RoadNode(Base):
    __tablename__ = "road_nodes"

    id = Column(Integer, primary_key=True, index=True)
    geom = Column(Geometry(geometry_type='POINT', srid=4326, spatial_index=True), nullable=False)
    # Inherited columns: created_at

    def __repr__(self):
        return f"<RoadNode id={self.id} geom={self.geom}>"