import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.incident_service import IncidentService
from app.db.models import User, RoadSegment
from app.db.models.incident import IncidentStatus
from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_simple_create_incident(db_session: AsyncSession):
    """Simple test using the fixture correctly"""
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

    # The db_session fixture already sets up execute to return a mock result
    # We just need to override what scalar_one_or_none returns for our specific case
    # Get the current mock result that execute returns
    mock_result = db_session.execute.return_value
    # Override scalar_one_or_none to return our segment ID
    mock_result.scalar_one_or_none.return_value = segment.id

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
    assert incident.segment_id == segment.id

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
