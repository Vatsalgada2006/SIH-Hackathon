import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.incident_service import IncidentService
from app.services.accessibility_service import AccessibilityService
from app.db.models import User, Incident, RoadSegment
from app.db.models.incident import IncidentStatus
from unittest.mock import MagicMock

def create_mock_result_scalar(value):
    """Create a mock result that returns the given value when scalar_one_or_none() is called."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = value
    return mock_result

@pytest.mark.asyncio
async def test_integration_workflow_field_officer_create_then_control_room_verify_resolve(db_session: AsyncSession):
    # Create a FIELD_OFFICER user
    field_officer = User(
        id=1,
        username="fieldofficer",
        email="field@example.com",
        password_hash="hashed",
        role="FIELD_OFFICER",
        is_active=True
    )
    # Create a CONTROL_ROOM user
    control_room = User(
        id=2,
        username="controlroom",
        email="control@example.com",
        password_hash="hashed",
        role="CONTROL_ROOM",
        is_active=True
    )
    db_session.add_all([field_officer, control_room])
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

    # Create a mock incident object that will be returned by get_incident
    mock_incident = MagicMock()
    mock_incident.id = 1
    mock_incident.verified_at = None
    mock_incident.verified_by = None
    mock_incident.status = None

    # Mock results for the execute method
