import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.accessibility_service import AccessibilityService
from app.db.models import RoadSegment
from app.db.models.incident import IncidentStatus

class MockIncident:
    def __init__(self, incident_type, severity, segment_id, status):
        self.incident_type = incident_type
        self.severity = severity
        self.segment_id = segment_id
        self.status = status

def create_mock_result(incidents):
    """Create a mock result that returns the given list of incidents when scalars().all() is called."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = incidents
    mock_result.scalars.return_value = mock_scalars
    return mock_result

async def test_debug():
    """Debug test to see what's happening"""
    print("=== Debug Test ===")
    
    # Setup mock session
    db_session = AsyncMock(spec=AsyncSession)
    
    # Create a mock segment with manual override set to OPEN
    mock_segment = MagicMock(spec=RoadSegment)
    mock_segment.id = 1
    mock_segment.status = "OPEN"  # What it would be without incidents
    mock_segment.manual_override = True
    mock_segment.manual_override_reason = "Manual override for testing"
    
    # Mock the execute method to return our segment when queried for manual override check
    mock_segment_result = MagicMock()
    mock_segment_result.scalar_one_or_none.return_value = mock_segment
    
    # Create a blocking incident
    blocking_incident = MockIncident(
        incident_type="LANDSLIDE",
        severity="HIGH",  # This is blocking
        segment_id=1,
        status=IncidentStatus.VERIFIED.value
    )
    
    print(f"Created incident: {blocking_incident.incident_type}, {blocking_incident.severity}")
    
    # Import the service to test the blocking logic directly
    from app.services.accessibility_service import AccessibilityService
    is_blocking = AccessibilityService._is_blocking_incident(blocking_incident.incident_type, blocking_incident.severity)
    print(f"_is_blocking_incident({blocking_incident.incident_type}, {blocking_incident.severity}) = {is_blocking}")
    
    # Mock for checking active incidents (would return our blocking incident)
    mock_incidents_result = MagicMock()
    mock_incidents_scalars = MagicMock()
    mock_incidents_scalars.all.return_value = [blocking_incident]
    mock_incidents_result.scalars.return_value = mock_incidents_scalars
    
    mock_update_result = MagicMock()
    mock_update_result.scalars.return_value.all.return_value = []
    
    # Set up side effects for the sequence of calls in update_segment_accessibility:
    # 1. Check for manual override (returns our segment) - only if force=False
    # 2. Calculate what the status SHOULD be based on incidents (requires checking for incidents)
    # 3. Update the segment with the new status
    db_session.execute.side_effect = [
        mock_segment_result,       # 1. Check manual override (returns segment)
        mock_incidents_result,     # 2. Check for incidents (returns blocking incident)
        mock_update_result         # 3. Update segment
    ]
    
    db_session.commit = AsyncMock()
    
    service = AccessibilityService(db_session)
    
    # First, let's test calculate_segment_accessibility directly
    print("\\n--- Testing calculate_segment_accessibility directly ---")
    # We need to mock the _get_active_verifed_incidents_for_segment method
    original_method = service._get_active_verifed_incidents_for_segment
    service._get_active_verifed_incidents_for_segment = AsyncMock(return_value=[blocking_incident])
    
    result = await service.calculate_segment_accessibility(1)
    print(f"calculate_segment_accessibility result: {result}")
    
    # Restore the method
    service._get_active_verifed_incidents_for_segment = original_method
    
    # Now test the full update
    print("\\n--- Testing update_segment_accessibility with force=True ---")
    # Reset side effects
    db_session.execute.side_effect = [
        mock_segment_result,       # 1. Check manual override (returns segment)
        mock_incidents_result,     # 2. Check for incidents (returns blocking incident)
        mock_update_result         # 3. Update segment
    ]
    
    result = await service.update_segment_accessibility(1, force=True)
    print(f"update_segment_accessibility(force=True) result: {result}")

if __name__ == "__main__":
    asyncio.run(test_debug())
