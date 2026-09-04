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

async def test_scenario_1_admin_sets_open_then_incident_verifies():
    """Scenario: ADMIN manually sets segment to OPEN, then a blocking incident is verified.
    Expected: Automatic logic should override it back to BLOCKED."""
    print("\\n=== Scenario 1: Admin sets OPEN, then blocking incident verifies ===")
    
    # Setup mock session
    db_session = AsyncMock(spec=AsyncSession)
    
    # Step 1: Admin manually sets segment to OPEN (with manual override)
    mock_segment_after_admin = MagicMock(spec=RoadSegment)
    mock_segment_after_admin.id = 1
    mock_segment_after_admin.status = "OPEN"  # What admin set
    mock_segment_after_admin.manual_override = True  # Admin set it
    mock_segment_after_admin.manual_override_reason = "Admin manually opened for maintenance"
    
    # Mock for the manual update check
    mock_segment_result = MagicMock()
    mock_segment_result.scalar_one_or_none.return_value = mock_segment_after_admin
    
    mock_update_result = MagicMock()
    
    # For step 1: check manual override, then update
    db_session.execute.side_effect = [mock_segment_result, mock_update_result]
    db_session.commit = AsyncMock()
    db_session.refresh = AsyncMock()
    db_session.add = MagicMock()
    
    service = AccessibilityService(db_session)
    
    # Verify manual override is respected
    result = await service.calculate_segment_accessibility(1)
    print(f"After admin manual OPEN: {result}")
    assert result == "OPEN", f"Expected OPEN after manual override, got {result}"
    
    # Step 2: A blocking incident occurs and is verified
    # Now we need to test what happens when we recalculate accessibility
    # We'll simulate there being a blocking incident
    
    blocking_incident = MockIncident(
        incident_type="LANDSLIDE",
        severity="HIGH",  # This makes it blocking
        segment_id=1,
        status=IncidentStatus.VERIFIED.value
    )
    
    # Mock for checking active incidents (would return our blocking incident)
    mock_incidents_result = MagicMock()
    mock_incidents_scalars = MagicMock()
    mock_incidents_scalars.all.return_value = [blocking_incident]
    mock_incidents_result.scalars.return_value = mock_incidents_scalars
    
    # Create FRESH mocks for this step to avoid side_effect exhaustion
    mock_segment_result_2 = MagicMock()
    mock_segment_result_2.scalar_one_or_none.return_value = mock_segment_after_admin  # Same segment
    
    mock_update_result_2 = MagicMock()
    
    # For step 2: 
    # 1. Check for manual override (returns our segment)
    # 2. Check for active incidents (returns blocking incident)  
    # 3. Update segment (if needed)
    db_session.execute.side_effect = [
        mock_segment_result_2,         # 1. Check manual override
        mock_incidents_result,         # 2. Check active incidents
        mock_update_result_2           # 3. Update segment
    ]
    
    # Now test the accessibility calculation - should still return OPEN due to manual override
    result = await service.calculate_segment_accessibility(1)
    print(f"After checking for blocking incidents (should still respect manual override): {result}")
    # calculate_segment_accessibility SHOULD still respect manual override
    assert result == "OPEN", f"Expected OPEN (still respecting manual override), got {result}"
    
    # But when we update with force=True (as done after incident verification), it should override
    result = await service.update_segment_accessibility(1, force=True)
    print(f"After force update (should reflect blocking incident): {result}")
    # Since we have a blocking incident, this should be BLOCKED
    assert result == "BLOCKED", f"Expected BLOCKED after force update with blocking incident, got {result}"
    
    print("✓ Scenario 1 PASSED: Admin OPEN -> Blocking incident correctly overrides to BLOCKED")

async def test_scenario_2_admin_sets_blocked_no_incidents_then_recalculate():
    """Scenario: ADMIN manually sets segment to BLOCKED with no incidents, then recalculate.
    Expected: Automatic logic should reset it to OPEN."""
    print("\\n=== Scenario 2: Admin sets BLOCKED with no incidents, then recalculate ===")
    
    # Setup mock session
    db_session = AsyncMock(spec=AsyncSession)
    
    # Step 1: Admin manually sets segment to BLOCKED (with manual override)
    mock_segment_after_admin = MagicMock(spec=RoadSegment)
    mock_segment_after_admin.id = 1
    mock_segment_after_admin.status = "BLOCKED"  # What admin set
    mock_segment_after_admin.manual_override = True  # Admin set it
    mock_segment_after_admin.manual_override_reason = "Admin manually blocked due to perceived threat"
    
    # Mock for the manual update check
    mock_segment_result = MagicMock()
    mock_segment_result.scalar_one_or_none.return_value = mock_segment_after_admin
    
    mock_update_result = MagicMock()
    
    # For step 1: check manual override, then update
    db_session.execute.side_effect = [mock_segment_result, mock_update_result]
    db_session.commit = AsyncMock()
    db_session.refresh = AsyncMock()
    db_session.add = MagicMock()
    
    service = AccessibilityService(db_session)
    
    # Verify manual override is respected
    result = await service.calculate_segment_accessibility(1)
    print(f"After admin manual BLOCKED (no incidents): {result}")
    assert result == "BLOCKED", f"Expected BLOCKED after manual override, got {result}"
    
    # Step 2: Recalculate accessibility with NO active incidents
    # Mock for checking active incidents (would return empty list - no incidents)
    mock_empty_incidents_result = MagicMock()
    mock_empty_incidents_scalars = MagicMock()
    mock_empty_incidents_scalars.all.return_value = []  # No incidents
    mock_empty_incidents_result.scalars.return_value = mock_empty_incidents_scalars
    
    # Create FRESH mocks for this step to avoid side_effect exhaustion
    mock_segment_result_2 = MagicMock()
    mock_segment_result_2.scalar_one_or_none.return_value = mock_segment_after_admin  # Same segment
    
    mock_update_result_2 = MagicMock()
    
    # For step 2: 
    # 1. Check for manual override (returns our segment)
    # 2. Check for active incidents (returns empty list)
    # 3. Update segment (if needed)
    db_session.execute.side_effect = [
        mock_segment_result_2,         # 1. Check manual override
        mock_empty_incidents_result,   # 2. Check active incidents (none)
        mock_update_result_2           # 3. Update segment
    ]
    
    # Now test the accessibility calculation - should still return BLOCKED due to manual override
    result = await service.calculate_segment_accessibility(1)
    print(f"After checking for no incidents (should still respect manual override): {result}")
    # calculate_segment_accessibility SHOULD still respect manual override
    assert result == "BLOCKED", f"Expected BLOCKED (still respecting manual override), got {result}"
    
    # But when we update with force=True (as done periodically or after incident changes), 
    # it should reset to OPEN since there are no incidents
    result = await service.update_segment_accessibility(1, force=True)
    print(f"After force update with no incidents (should reset to OPEN): {result}")
    # Since we have no incidents, this should be OPEN
    assert result == "OPEN", f"Expected OPEN after force update with no incidents, got {result}"
    
    print("✓ Scenario 2 PASSED: Admin BLOCKED -> No incidents correctly resets to OPEN")

async def run_scenario_tests():
    await test_scenario_1_admin_sets_open_then_incident_verifies()
    await test_scenario_2_admin_sets_blocked_no_incidents_then_recalculate()
    print("\\n🎉 All scenario tests PASSED!")

if __name__ == "__main__":
    asyncio.run(run_scenario_tests())
