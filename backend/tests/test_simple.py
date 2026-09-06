import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.incident_service import IncidentService
from app.db.models import User
from app.db.models.incident import IncidentStatus
from unittest.mock import MagicMock
from geoalchemy2.elements import WKTElement
from geoalchemy2.functions import ST_SetSRID, ST_MakePoint
from sqlalchemy import func

def test_point_creation():
    """Test that point creation works correctly"""
    longitude = 0.0
    latitude = 0.0
    point = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
    print(f"Point type: {type(point)}")
    print(f"Point: {point}")
    return point

if __name__ == "__main__":
    test_point_creation()
