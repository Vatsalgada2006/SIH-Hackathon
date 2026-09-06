import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.incident_service import IncidentService
from app.db.models import User, RoadSegment
from app.db.models.incident import IncidentStatus

@pytest.mark.asyncio
async def test_simple_create_incident(db_session: AsyncSession):
    """Simple test using the fixture"""
    # Create a FIELD_OFFICER user
    field_officer = User(
        id=1,
        username="fieldofficer",
        email="field@example.com",
        password_hash="hashed",
        role="FIELD_OFFICER",
        is_active=True
    )
    db_session.add(field_officer)
    await db_session.commit()

    # Create a road segment
    segment = RoadSegment(
        id=1,
        start_node_id=1,
        end_node_id=2,
        status="UNKNOWN"
    )
    db_session.add(segment)
    await db_session.commit()

    # Override the execute method to return our segment for the nearest query
    from unittest.mock import MagicMock
    from geoalchemy2.functions import ST_Distance
    
    # Create a mock result that returns our segment ID
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = segment.id
    
    # Set the execute method to return this mock result
    db_session.execute = MagicMock(return_value=mock_result)
    
    # Also need to mock commit and refresh
    db_session.commit = MagicMock()
    db_session.refresh = MagicMock()
    
    incident_service = IncidentService(db_session)
    incident = await incident_service.create_incident(
        reporter_id=field_officer.id,
        description="Test incident",
        incident_type="LANDSLIDE",
        severity="HIGH",
        latitude=0.0,
        longitude=0.0,
        segment_id=None
    )
    
    print(f"Created incident: {incident}")
    assert incident is not None

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
