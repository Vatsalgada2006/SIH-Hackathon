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

def create_mock_result_scalars(values):
    """Create a mock result that returns the given values when scalars().all() is called."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = values
    mock_result.scalars.return_value = mock_salars
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

    # We'll track the state of our mock incident through the test
    mock_incident_state = {
        "id": 1,
        "verified_at": None,
        "verified_by": None,
        "status": None,  # Will be PENDING, then VERIFIED, then RESOLVED
        "resolved_at": None,
        "incident_type": "LANDSLIDE",
        "severity": "HIGH",
        "segment_id": 1
    }

    def create_mock_incident_from_state():
        """Create a mock incident object based on current state."""
        mock_incident = MagicMock()
        mock_incident.id = mock_incident_state["id"]
        mock_incident.verified_at = mock_incident_state["verified_at"]
        mock_incident.verified_by = mock_incident_state["verified_by"]
        mock_incident.status = mock_incident_state["status"]
        mock_incident.resolved_at = mock_incident_state["resolved_at"]
        mock_incident.incident_type = mock_incident_state["incident_type"]
        mock_incident.severity = mock_incident_state["severity"]
        mock_incident.segment_id = mock_incident_state["segment_id"]
        return mock_incident

    # Set up side effect for execute with a function that can track state
    call_count = 0
    
    async def execute_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        
        if call_count == 1:
            # First call: nearest segment query in create_incident
            return create_mock_result_scalar(segment.id)
        elif call_count == 2:
            # Second call: get incident after creation in create_incident (for refresh or similar)
            # We need to return an incident object with PENDING status
            mock_incident_state["status"] = IncidentStatus.PENDING.value
            return create_mock_result_scalar(create_mock_incident_from_state())
        elif call_count == 3:
            # Third call: get incident in verify_incident
            # Incident should still be PENDING when we fetch it to verify
            return create_mock_result_scalar(create_mock_incident_from_state())
        elif call_count == 4:
            # Fourth call: get verified incidents for accessibility check after verification
            # After verification, incident should be VERIFIED
            mock_incident_state["status"] = IncidentStatus.VERIFIED.value
            mock_incident_state["verified_at"] = "some_timestamp"
            mock_incident_state["verified_by"] = control_room.id
            return create_mock_result_scalars([create_mock_incident_from_state()])
        elif call_count == 5:
            # Fifth call: get incident in resolve_incident
            # Incident should be VERIFIED when we fetch it to resolve
            return create_mock_result_scalar(create_mock_incident_from_state())
        elif call_count == 6:
            # Sixth call: get verified incidents for accessibility check after resolution
            # After resolution, incident should be RESOLVED, so not included in active incidents
            mock_incident_state["status"] = IncidentStatus.RESOLVED.value
            mock_incident_state["resolved_at"] = "some_timestamp"
            return create_mock_result_scalars([])  # Empty list - no active verified incidents
        else:
            # Default: return empty result
            return create_mock_result_scalar(None)

    # Set up the side effect for execute
    db_session.execute.side_effect = execute_side_effect
    
    # Also need to mock commit and refresh
    db_session.commit = MagicMock()
    db_session.refresh = MagicMock()

    # Step 1: FIELD_OFFICER creates a LANDSLIDE incident
    incident_service = IncidentService(db_session)
    incident = await incident_service.create_incident(
        reporter_id=field_officer.id,
        description="Landslide on the road",
        incident_type="LANDSLIDE",
        severity="HIGH",
        latitude=0.0,
        longitude=0.0,
        segment_id=None  # Let the service find the nearest segment
    )
    assert incident is not None
    assert incident.status == IncidentStatus.PENDING.value
    # The service should have set the segment_id to the nearest segment (which is our segment)
    assert incident.segment_id == 1
    incident.id = 1

    # After creation, the incident is PENDING, so it should not affect accessibility yet
    accessibility_service = AccessibilityService(db_session)
    status_after_create = await accessibility_service.calculate_segment_accessibility(1)
    assert status_after_create == "OPEN"  # PENDING incident does not affect accessibility

    # Step 2: CONTROL_ROOM veries the incident
    verified_incident = await incident_service.verify_incident(incident.id, control_room.id)
    assert verified_incident is not None
    assert verified_incident.status == IncidentStatus.VERIFIED.value
    assert verified_incident.verified_by == control_room.id

    # After verification, the incident is VERIFIED and active, so it should affect accessibility
    status_after_verify = await accessibility_service.calculate_segment_accessibility(1)
    # Since the incident is LANDSLIDE with HIGH severity, it should be BLOCKED
    assert status_after_verify == "BLOCKED"

    # Step 3: CONTROL_ROOM resolves the incident
    resolved_incident = await incident_service.resolve_incident(incident.id)
    assert resolved_incident is not None
    assert resolved_incident.status == IncidentStatus.RESOLVED.value
    assert resolved_incident.resolved_at is not None

    # After resolution, there are no active verified incidents, so the segment should be OPEN
    status_after_resolve = await accessibility_service.calculate_segment_accessibility(1)
    assert status_after_resolve == "OPEN"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
