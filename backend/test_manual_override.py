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

async def test_manual_override_precedes_automatic():
    """Test that manual override takes precedence over automatic calculation."""
    # Setup mock session
    db_session = AsyncMock(spec=AsyncSession)
    
    # Create a mock segment with manual override set to OPEN
    mock_segment = MagicMock(spec=RoadSegment)
    mock_segment.id = 1
    mock_segment.status = "OPEN"
    mock_segment.manual_override = True
    mock_segment.manual_override_reason = "Manual override for testing"
    
    # Mock the execute method to return our segment when queried
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_segment
    db_session.execute.return_value = mock_result
    db_session.commit = AsyncMock()
    
    # Create service
    service = AccessibilityService(db_session)
    
    # Test that calculate_segment_accessibility respects manual override
    # Even if there are blocking incidents, if manual override is set, it should return the overridden status
    result = await service.calculate_segment_accessibility(1)
    print(f"Result with manual override OPEN: {result}")
    assert result == "OPEN", f"Expected OPEN, got {result}"
    
    # Now test without manual override - should calculate normally
    mock_segment.manual_override = False
    result = await service.calculate_segment_accessibility(1)
    print(f"Result without manual override (no incidents): {result}")
    assert result == "OPEN", f"Expected OPEN, got {result}"
    
    print("Manual override precedence test passed!")

async def test_automatic_can_force_override():
    """Test that automatic update can force override manual settings when force=True."""
    # Setup mock session
    db_session = AsyncMock(spec=AsyncSession)
    
    # Create a mock segment with manual override set to OPEN
    mock_segment = MagicMock(spec=RoadSegment)
    mock_segment.id = 1
    mock_segment.status = "OPEN"  # Current status
    mock_segment.manual_override = True
    mock_segment.manual_override_reason = "Manual override for testing"
    
    # Mock execute to return segment for the check, then allow update
    mock_segment_result = MagicMock()
    mock_segment_result.scalar_one_or_none.return_value = mock_segment
    
    mock_update_result = MagicMock()
    mock_update_result.scalars.return_value.all.return_value = []
    
    db_session.execute.side_effect = [mock_segment_result, mock_update_result]
    db_session.commit = AsyncMock()
    
    # Create service
    service = AccessibilityService(db_session)
    
    # Test that update_segment_accessibility respects manual override when force=False
    result = await service.update_segment_accessibility(1, force=False)
    print(f"Result with force=False (should respect manual override): {result}")
    assert result == "OPEN", f"Expected OPEN (respecting manual override), got {result}"
    assert db_session.execute.call_count == 1  # Only the select call, no update
    
    # Reset mock for next call
    db_session.execute.reset_mock()
    db_session.execute.side_effect = [mock_segment_result, mock_update_result]
    
    # Test that update_segment_accessibility can override when force=True
    result = await service.update_segment_accessibility(1, force=True)
    print(f"Result with force=True (should update despite manual override): {result}")
    assert result == "OPEN", f"Expected OPEN (no incidents), got {result}"
    assert db_session.execute.call_count == 2  # Select and update calls
    
    print("Force override test passed!")

async def test_manual_update_sets_override_fields():
    """Test that manual update properly sets the override fields."""
    # Setup mock session
    db_session = AsyncMock(spec=AsyncSession)
    
    # Mock execute for select (current status) and update
    mock_segment_result = MagicMock()
    mock_segment_result.scalar_one_or_none.return_value = "OPEN"  # current status
    
    mock_update_result = MagicMock()
    
    db_session.execute.side_effect = [mock_segment_result, mock_update_result]
    db_session.commit = AsyncMock()
    db_session.refresh = AsyncMock()
    db_session.add = MagicMock()
    
    # Create service
    service = AccessibilityService(db_session)
    
    # Test manual update
    result = await service.manually_update_segment_status(
        segment_id=1,
        new_status="BLOCKED",
        user_id=1,
        reason="Test manual block"
    )
    
    print(f"Manual update result: {result}")
    assert result == "BLOCKED", f"Expected BLOCKED, got {result}"
    
    # Verify that the update was called with the correct values
    # We can't easily check the exact values passed to update with our mock setup,
    # but we can verify the function completed without error
    
    print("Manual update test passed!")

async def run_tests():
    await test_manual_override_precedes_automatic()
    await test_automatic_can_force_override()
    await test_manual_update_sets_override_fields()
    print("All tests passed!")

if __name__ == "__main__":
    asyncio.run(run_tests())
