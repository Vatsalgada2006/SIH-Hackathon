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

async def test_scenario_1_admin_open_then_blocking_incident():
    """Scenario 1: ADMIN manually sets segment to OPEN, then blocking incident verified -> should override to BLOCKED"""
    print("=== SCENARIO 1: Admin OPEN -> Blocking Incident -> Should become BLOCKED ===")
    
    # Setup mock session
    db_session = AsyncMock(spec=AsyncSession)
    
    # Create a mock segment that was manually set to OPEN by admin
    mock_segment = MagicMock(spec=RoadSegment)
    mock_segment.id = 1
    mock_segment.status = "OPEN"  # Manually set to OPEN
    mock_segment.manual_override = True  # Has manual override
    mock_segment.manual_override_reason = "Admin manually opened for testing"
    
    # Mock for checking active incidents (would return our blocking incident)
    blocking_incident = MockIncident(
        incident_type="LANDSLIDE",
        severity="HIGH",  # This is blocking
        segment_id=1,
        status=IncidentStatus.VERIFIED.value
    )
    
    mock_incidents_result = MagicMock()
    mock_incidents_scalars = MagicMock()
    mock_incidents_scalars.all.return_value = [blocking_incident]
    mock_incidents_result.scalars.return_value = mock_incidents_scalars
    
    mock_update_result = MagicMock()
    mock_update_result.scalars.return_value.all.return_value = []
    
    # When force=True (called from incident verification), it should:
    # 1. Check for active incidents (finds blocking incident)
    # 2. Update the segment despite manual override
    db_session.execute.side_effect = [
        mock_incidents_result,     # 1. Incidents query (from calculate_segment_accessibility)
        mock_update_result         # 2. Update statement (from update_segment_accessibility)
    ]
    
    db_session.commit = AsyncMock()
    
    service = AccessibilityService(db_session)
    
    # Test: Even with manual override set to OPEN, when incident is verified (force=True),
    # it should change to BLOCKED because there's a blocking incident
    result = await service.update_segment_accessibility(1, force=True)
    print(f"Result after blocking incident verification: {result}")
    assert result == "BLOCKED", f"Expected BLOCKED due to blocking incident, got {result}"
    print("✓ PASS: Blocking incident correctly overrides manual OPEN override")
    
    return True

async def test_scenario_2_admin_blocked_no_incidents():
    """Scenario 2: Admin manually sets segment to BLOCKED with no active incidents -> should reset to OPEN on recalculation"""
    print("\\n=== SCENARIO 2: Admin BLOCKED (no incidents) -> Should become OPEN ===")
    
    # Setup mock session
    db_session = AsyncMock(spec=AsyncSession)
    
    # Create a mock segment that was manually set to BLOCKED by admin
    mock_segment = MagicMock(spec=RoadSegment)
    mock_segment.id = 1
    mock_segment.status = "BLOCKED"  # Manually set to BLOCKED
    mock_segment.manual_override = True  # Has manual override
    mock_segment.manual_override_reason = "Admin manually blocked for testing"
    
    # Mock for checking active incidents (would return empty list - no incidents)
    mock_empty_incidents_result = MagicMock()
    mock_empty_incidents_scalars = MagicMock()
    mock_empty_incidents_scalars.all.return_value = []  # No incidents
    mock_empty_incidents_result.scalars.return_value = mock_empty_incidents_scalars
    
    mock_update_result = MagicMock()
    mock_update_result.scalars.return_value.all.return_value = []
    
    # When force=True (called from incident resolution or manual recalculation), it should:
    # 1. Check for active incidents (finds none)
    # 2. Update the segment to OPEN despite manual override
    db_session.execute.side_effect = [
        mock_empty_incidents_result, # 1. Incidents query (none)
        mock_update_result         # 2. Update statement
    ]
    
    db_session.commit = AsyncMock()
    
    service = AccessibilityService(db_session)
    
    # Test: Even with manual override set to BLOCKED, when we force an update
    # with no incidents, it should change to OPEN
    result = await service.update_segment_accessibility(1, force=True)
    print(f"Result after checking incidents (none found): {result}")
    assert result == "OPEN", f"Expected OPEN due to no incidents, got {result}"
    print("✓ PASS: No incidents correctly overrides manual BLOCKED override")
    
    return True

async def test_manual_override_respected_when_not_forced():
    """Verify that manual override is respected when force=False (normal operation)"""
    print("\\n=== VERIFICATION: Manual override respected when force=False ===")
    
    # Setup mock session
    db_session = AsyncMock(spec=AsyncSession)
    
    # Create a mock segment with manual override set to OPEN
    mock_segment = MagicMock(spec=RoadSegment)
    mock_segment.id = 1
    mock_segment.status = "OPEN"  # What it was manually set to
    mock_segment.manual_override = True
    mock_segment.manual_override_reason = "Manual override for testing"
    
    # Mock the execute method to return our segment when queried
    mock_segment_result = MagicMock()
    mock_segment_result.scalar_one_or_none.return_value = mock_segment
    
    # Mock update result (should not be called when force=False and manual_override=True)
    mock_update_result = MagicMock()
    
    # Set up side effects
    db_session.execute.side_effect = [
        mock_segment_result,       # 1. Segment query (for manual override check)
        mock_update_result         # 2. Update statement (should NOT be called)
    ]
    
    db_session.commit = AsyncMock()
    
    service = AccessibilityService(db_session)
    
    # Test: When force=False, manual override should be respected
    result = await service.update_segment_accessibility(1, force=False)
    print(f"Result with force=False and manual override OPEN: {result}")
    assert result == "OPEN", f"Expected OPEN (respecting manual override), got {result}"
    
    # Verify update was NOT called (only the segment check query should have been executed)
    # We expect exactly 1 call (the segment check) because manual_override=True and force=False
    assert db_session.execute.call_count == 1, f"Expected 1 execute call (only for segment check), got {db_session.execute.call_count}"
    print("✓ PASS: Manual override correctly respected when force=False")
    
    return True

async def run_all_tests():
    """Run all test scenarios"""
    print("Starting comprehensive tests for manual override functionality...\n")
    
    try:
        await test_scenario_1_admin_open_then_blocking_incident()
        await test_scenario_2_admin_blocked_no_incidents()
        await test_manual_override_respected_when_not_forced()
        
        print("\\n" + "="*60)
        print("🎉 ALL TESTS PASSED!")
        print("✅ Scenario 1: Admin OPEN -> Blocking Incident -> BLOCKED (override works)")
        print("✅ Scenario 2: Admin BLOCKED (no incidents) -> OPEN (override works)")
        print("✅ Verification: Manual override respected when not forced")
        print("="*60)
        print("\\nThe manual override functionality is working correctly!")
        print("Both scenarios specified by the user have been verified.")
        
        return True
        
    except Exception as e:
        print(f"\\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
