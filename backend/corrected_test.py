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

async def test_with_blocking_incidents_corrected():
    """Test that when there are blocking incidents, the status changes appropriately"""
    print("=== Testing with Blocking Incidents (Corrected) ===")
    
    # Setup mock session
    db_session = AsyncMock(spec=AsyncSession)
    
    # Create a mock segment with manual override set to OPEN
    mock_segment = MagicMock(spec=RoadSegment)
    mock_segment.id = 1
    mock_segment.status = "OPEN"  # What it would be without incidents
    mock_segment.manual_override = True
    mock_segment.manual_override_reason = "Manual override for testing"
    
    # Mock the execute method to return our segment when queried for manual override check
    # Note: We won't actually check manual override because we're using force=True
    mock_segment_result = MagicMock()
    mock_segment_result.scalar_one_or_none.return_value = mock_segment
    
    # Create a blocking incident
    blocking_incident = MockIncident(
        incident_type="LANDSLIDE",
        severity="HIGH",  # This is blocking
        segment_id=1,
        status=IncidentStatus.VERIFIED.value
    )
    
    # Mock for checking active incidents (would return our blocking incident)
    mock_incidents_result = MagicMock()
    mock_incidents_scalars = MagicMock()
    mock_incidents_scalars.all.return_value = [blocking_incident]
    mock_incidents_result.scalars.return_value = mock_incidents_scalars
    
    mock_update_result = MagicMock()
    mock_update_result.scalars.return_value.all.return_value = []
    
    # Set up side effects for the sequence of calls:
    # 1. From _get_active_verifed_incidents_for_segment (incidents query) - FIRST
    # 2. From the update statement - SECOND
    db_session.execute.side_effect = [
        mock_incidents_result,     # 1. Incidents query
        mock_update_result         # 2. Update statement
    ]
    
    db_session.commit = AsyncMock()
    
    service = AccessibilityService(db_session)
    
    # Test: Even with manual override set to OPEN, when we force an update,
    # it should change to BLOCKED because there's a blocking incident
    result = await service.update_segment_accessibility(1, force=True)
    print(f"Result with blocking incident and force=True: {result}")
    assert result == "BLOCKED", f"Expected BLOCKED due to blocking incident, got {result}"
    print("✓ Blocking incident correctly overrides manual OPEN override")
    
    # Now test the reverse: manual override set to BLOCKED but no incidents
    # Should reset to OPEN when forced
    
    # Create a mock segment with manual override set to BLOCKED
    mock_segment2 = MagicMock(spec=RoadSegment)
    mock_segment2.id = 1
    mock_segment2.status = "BLOCKED"  # What it would be without incidents
    mock_segment2.manual_override = True
    mock_segment2.manual_override_reason = "Manual override for testing"
    
    # Mock for checking active incidents (would return empty list - no incidents)
    mock_empty_incidents_result = MagicMock()
    mock_empty_incidents_scalars = MagicMock()
    mock_empty_incidents_scalars.all.return_value = []  # No incidents
    mock_empty_incidents_result.scalars.return_value = mock_empty_incidents_scalars
    
    # Mock segment result for this test
    mock_segment_result_2 = MagicMock()
    mock_segment_result_2.scalar_one_or_none.return_value = mock_segment2
    
    # Set up side effects
    db_session.execute.side_effect = [
        mock_empty_incidents_result, # 1. Incidents query (none)
        mock_update_result         # 2. Update statement
    ]
    
    # Test: Even with manual override set to BLOCKED, when we force an update
    # with no incidents, it should change to OPEN
    result = await service.update_segment_accessibility(1, force=True)
    print(f"Result with no incidents and force=True: {result}")
    assert result == "OPEN", f"Expected OPEN due to no incidents, got {result}"
    print("✓ No incidents correctly overrides manual BLOCKED override")
    
    print("\\n🎉 All incident override tests PASSED!")
    
    # Also test that manual override is respected when force=False
    print("\\n--- Testing that manual override is respected when force=False ---")
    db_session.execute.side_effect = [
        mock_segment_result,       # 1. Segment query (for manual override check)
        mock_update_result         # 2. Update statement (should not be called)
    ]
    
    result = await service.update_segment_accessibility(1, force=False)
    print(f"Result with force=False and manual override OPEN: {result}")
    assert result == "OPEN", f"Expected OPEN (respecting manual override), got {result}"
    # Verify update was NOT called
    assert db_session.execute.call_count == 1, f"Expected 1 execute call (only for segment check), got {db_session.execute.call_count}"
    print("✓ Manual override correctly respected when force=False")

if __name__ == "__main__":
    asyncio.run(test_with_blocking_incidents_corrected())
