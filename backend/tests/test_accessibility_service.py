import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from unittest.mock import MagicMock
from app.services.accessibility_service import AccessibilityService
from app.db.models.incident import IncidentStatus
from unittest.mock import AsyncMock

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

@pytest.mark.asyncio
async def test_is_blocking_incident():
    # Test blocking incidents
    assert AccessibilityService._is_blocking_incident(None, None) == False
    assert AccessibilityService._is_blocking_incident("LANDSLIDE", "HIGH") == True
    assert AccessibilityService._is_blocking_incident("LANDSLIDE", "CRITICAL") == True
    assert AccessibilityService._is_blocking_incident("LANDSLIDE", "MEDIUM") == False
    assert AccessibilityService._is_blocking_incident("LANDSLIDE", "LOW") == False
    assert AccessibilityService._is_blocking_incident("FLOOD", "HIGH") == True
    assert AccessibilityService._is_blocking_incident("FLOOD", "CRITICAL") == True
    assert AccessibilityService._is_blocking_incident("FLOOD", "MEDIUM") == False
    assert AccessibilityService._is_blocking_incident("FLOOD", "LOW") == False
    assert AccessibilityService._is_blocking_incident("ACCIDENT", "HIGH") == False  # Not blocking by default
    assert AccessibilityService._is_blocking_incident("CONSTRUCTION", "HIGH") == False  # Not blocking by default
    assert AccessibilityService._is_blocking_incident("OTHER", "HIGH") == False

@pytest.mark.asyncio
async def test_is_degrading_incident():
    # Test degrading incidents (not blocking)
    assert AccessibilityService._is_degrading_incident("LANDSLIDE", "HIGH") == False  # It's blocking, so not degrading
    assert AccessibilityService._is_degrading_incident("LANDSLIDE", "MEDIUM") == True
    assert AccessibilityService._is_degrading_incident("LANDSLIDE", "LOW") == True
    assert AccessibilityService._is_degrading_incident("FLOOD", "MEDIUM") == True
    assert AccessibilityService._is_degrading_incident("FLOOD", "LOW") == True
    assert AccessibilityService._is_degrading_incident("ACCIDENT", "HIGH") == True  # Accident is degrading
    assert AccessibilityService._is_degrading_incident("CONSTRUCTION", "HIGH") == True  # Construction is degrading
    assert AccessibilityService._is_degrading_incident("OTHER", "HIGH") == True  # Other is degrading (assuming)
    # Note: The _is_degrading_incident method returns True if not blocking, so for OTHER with HIGH, it's not blocking, so degrading.

@pytest.mark.asyncio
async def test_calculate_segment_accessibility_no_incidents(db_session):
    # Mock the execute method to return an empty list of incidents
    db_session.execute.return_value = create_mock_result([])
    db_session.commit = AsyncMock()

    service = AccessibilityService(db_session)
    status = await service.calculate_segment_accessibility(1)
    assert status == "OPEN"

@pytest.mark.asyncio
async def test_calculate_segment_accessibility_with_blocking_incident(db_session):
    # Create a mock incident
    incident = MockIncident(
        incident_type="LANDSLIDE",
        severity="HIGH",
        segment_id=1,
        status=IncidentStatus.VERIFIED.value,
    )
    # Mock the execute method to return a list containing this incident
    db_session.execute.return_value = create_mock_result([incident])
    db_session.commit = AsyncMock()

    service = AccessibilityService(db_session)
    status = await service.calculate_segment_accessibility(1)
    assert status == "BLOCKED"

@pytest.mark.asyncio
async def test_calculate_segment_accessibility_with_degrading_incident(db_session):
    # Create a mock incident
    incident = MockIncident(
        incident_type="LANDSLIDE",
        severity="MEDIUM",
        segment_id=1,
        status=IncidentStatus.VERIFIED.value,
    )
    # Mock the execute method to return a list containing this incident
    db_session.execute.return_value = create_mock_result([incident])
    db_session.commit = AsyncMock()

    service = AccessibilityService(db_session)
    status = await service.calculate_segment_accessibility(1)
    assert status == "DEGRADED"

@pytest.mark.asyncio
async def test_calculate_segment_accessibility_multiple_incidents_precedence(db_session):
    # Create a mock degrading incident
    incident1 = MockIncident(
        incident_type="LANDSLIDE",
        severity="MEDIUM",
        segment_id=1,
        status=IncidentStatus.VERIFIED.value,
    )
    # Create a mock blocking incident
    incident2 = MockIncident(
        incident_type="FLOOD",
        severity="HIGH",
        segment_id=1,
        status=IncidentStatus.VERIFIED.value,
    )
    # Mock the execute method to return a list containing both incidents
    db_session.execute.return_value = create_mock_result([incident1, incident2])
    db_session.commit = AsyncMock()

    service = AccessibilityService(db_session)
    status = await service.calculate_segment_accessibility(1)
    assert status == "BLOCKED"  # Blocking takes precedence

@pytest.mark.asyncio
async def test_update_segment_accessibility(db_session):
    # Create a mock incident
    incident = MockIncident(
        incident_type="LANDSLIDE",
        severity="MEDIUM",
        segment_id=1,
        status=IncidentStatus.VERIFIED.value,
    )
    # Mock the execute method for the select query to return the incident
    # We'll use a side_effect to return different results for select and update
    mock_update_result = MagicMock()
    mock_update_result.scalars.return_value.all.return_value = []
    db_session.execute.side_effect = [
        create_mock_result([incident]),  # first call: select incidents
        mock_update_result               # second call: update road segment
    ]
    db_session.commit = AsyncMock()

    service = AccessibilityService(db_session)
    new_status = await service.update_segment_accessibility(1, force=True)
    assert new_status == "DEGRADED"
    # Verify that commit was called
    assert db_session.commit.called

@pytest.mark.asyncio
async def test_manually_update_segment_status(db_session):
    # Mock the execute method for selecting the segment
    mock_segment_result = MagicMock()
    mock_segment_result.scalar_one_or_none.return_value = "OPEN"  # current status
    # Mock the execute method for updating the segment (we don't need to return anything)
    mock_update_result = MagicMock()
    # We'll set up side_effect on the execute method: first call for select, second for update
    db_session.execute.side_effect = [mock_segment_result, mock_update_result]
    # Mock commit and refresh
    db_session.commit = AsyncMock()
    db_session.refresh = AsyncMock()

    service = AccessibilityService(db_session)
    new_status = await service.manually_update_segment_status(
        segment_id=1,
        new_status="BLOCKED",
        user_id=1,
        reason="Test reason"
    )
    assert new_status == "BLOCKED"
    # Verify that commit was called twice (once for update, once for audit log)
    assert db_session.commit.call_count == 2
    # Verify that add was called for the audit log
    assert db_session.add.called


@pytest.mark.asyncio
async def test_update_segment_accessibility_respects_manual_override_when_false(db_session):
    """Test that update_segment_accessibility respects manual override when force=False"""
    # Mock a segment with manual override set to TRUE
    mock_segment = MagicMock()
    mock_segment.id = 1
    mock_segment.status = "OPEN"  # Current status
    mock_segment.manual_override = True  # Manual override is active

    # Mock the execute method to return a result object
    mock_result = MagicMock()
    # Make scalar_one_or_none return the segment directly (matching the pattern in existing tests)
    mock_result.scalar_one_or_none.return_value = mock_segment

    # Mock the execute method to return the result
    db_session.execute.return_value = mock_result

    # Mock commit
    db_session.commit = AsyncMock()

    service = AccessibilityService(db_session)

    # Even though there are incidents that would make it BLOCKED,
    # because manual_override is True and force=False, it should return the current status
    # Mock the calculate_segment_accessibility to return BLOCKED (what it would be without manual override)
    # But we won't actually call it because the method should return early

    # Actually, let's mock the calculate_segment_accessibility to verify it's NOT called
    original_calculate = service.calculate_segment_accessibility
    service.calculate_segment_accessibility = AsyncMock(return_value="BLOCKED")

    # Call update_segment_accessibility with force=False
    result = await service.update_segment_accessibility(1, force=False)

    # Should return the current status from the segment, not the calculated one
    assert result == "OPEN"
    # Verify that calculate_segment_accessibility was NOT called due to early return
    service.calculate_segment_accessibility.assert_not_called()

    # Restore the original method
    service.calculate_segment_accessibility = original_calculate


@pytest.mark.asyncio
async def test_update_segment_accessibility_overwrites_manual_override_when_true(db_session):
    """Test that update_segment_accessibility overwrites manual override when force=True"""
    # Mock a segment with manual override set to TRUE
    mock_segment = MagicMock()
    mock_segment.id = 1
    mock_segment.status = "OPEN"  # Current status
    mock_segment.manual_override = True  # Manual override is active

    # Mock the execute method to return a result object for the update query
    mock_result = MagicMock()

    # Mock the execute method to return the result (only one call for the update)
    db_session.execute.return_value = mock_result
    db_session.commit = AsyncMock()

    service = AccessibilityService(db_session)

    # Mock calculate_segment_accessibility to return BLOCKED
    service.calculate_segment_accessibility = AsyncMock(return_value="BLOCKED")

    # Call update_segment_accessibility with force=True
    result = await service.update_segment_accessibility(1, force=True)

    # Should return the calculated status, overwriting the manual override
    assert result == "BLOCKED"
    # Verify that calculate_segment_accessibility WAS called
    service.calculate_segment_accessibility.assert_called_once_with(1)
    # Verify that an update was executed (should be 1 execute call for the update when force=True)
    assert db_session.execute.call_count == 1
    # Verify that commit was called
    assert db_session.commit.called


@pytest.mark.asyncio
async def test_manual_override_respected_then_overridden_by_blocking_incident(db_session):
    """Test scenario 1: Admin manually sets segment to OPEN, then verifies blocking incident → automatic override to BLOCKED"""
    # Setup: Segment with manual override set to OPEN
    mock_segment = MagicMock()
    mock_segment.id = 1
    mock_segment.status = "OPEN"  # Manually set to OPEN
    mock_segment.manual_override = True  # Manual override is active

    # Mock the execute method for checking manual override (when force=False)
    mock_check_result = MagicMock()
    mock_check_result.scalar_one_or_none.return_value = mock_segment

    # Mock the execute method for the update (when force=True from incident verification)
    mock_update_result = MagicMock()

    # Set up side_effect: first call checks manual override, second call does the update
    db_session.execute.side_effect = [mock_check_result, mock_update_result]
    db_session.commit = AsyncMock()

    service = AccessibilityService(db_session)

    # Step 1: Verify that when force=False, manual override is respected (returns OPEN despite incidents)
    # Mock calculate_segment_accessibility to return BLOCKED (what it would be with incident)
    service.calculate_segment_accessibility = AsyncMock(return_value="BLOCKED")

    # Call update_segment_accessibility with force=False (simulating automatic update without force)
    result = await service.update_segment_accessibility(1, force=False)

    # Should return OPEN (respecting manual override)
    assert result == "OPEN"
    # Verify that calculate_segment_accessibility was NOT called due to early return
    service.calculate_segment_accessibility.assert_not_called()

    # Step 2: Simulate incident verification which calls update_segment_accessibility with force=True
    # This should overwrite the manual override and set status to BLOCKED
    service.calculate_segment_accessibility = AsyncMock(return_value="BLOCKED")  # Reset mock

    # Call update_segment_accessibility with force=True (simulating incident verification)
    result = await service.update_segment_accessibility(1, force=True)

    # Should return BLOCKED (overwriting manual override due to force=True)
    assert result == "BLOCKED"
    # Verify that calculate_segment_accessibility WAS called
    service.calculate_segment_accessibility.assert_called_once_with(1)
    # Verify that an update was executed
    assert db_session.execute.call_count == 2  # First call (check) + second call (update)
    # Verify that commit was called
    assert db_session.commit.called


@pytest.mark.asyncio
async def test_manual_override_overridden_by_no_incidents_returns_to_open(db_session):
    """Test scenario 2: Admin manually sets segment to BLOCKED with no active incidents → automatic recalculation → OPEN"""
    # Setup: Segment with manual override set to BLOCKED
    mock_segment = MagicMock()
    mock_segment.id = 1
    mock_segment.status = "BLOCKED"  # Manually set to BLOCKED
    mock_segment.manual_override = True  # Manual override is active

    # Mock the execute method for checking manual override (when force=False)
    mock_check_result = MagicMock()
    mock_check_result.scalar_one_or_none.return_value = mock_segment

    # Mock the execute method for the update (when force=True from incident resolution)
    mock_update_result = MagicMock()

    # Set up side_effect: first call checks manual override, second call does the update
    db_session.execute.side_effect = [mock_check_result, mock_update_result]
    db_session.commit = AsyncMock()

    service = AccessibilityService(db_session)

    # Step 1: Verify that when force=False, manual override is respected (returns BLOCKED despite no incidents)
    # Mock calculate_segment_accessibility to return OPEN (what it would be with no incidents)
    service.calculate_segment_accessibility = AsyncMock(return_value="OPEN")

    # Call update_segment_accessibility with force=False (simulating automatic update without force)
    result = await service.update_segment_accessibility(1, force=False)

    # Should return BLOCKED (respecting manual override)
    assert result == "BLOCKED"
    # Verify that calculate_segment_accessibility was NOT called due to early return
    service.calculate_segment_accessibility.assert_not_called()

    # Step 2: Simulate incident resolution (no active incidents) which calls update_segment_accessibility with force=True
    # This should overwrite the manual override and set status to OPEN
    service.calculate_segment_accessibility = AsyncMock(return_value="OPEN")  # Reset mock

    # Call update_segment_accessibility with force=True (simulating automatic recalculation with force=True)
    result = await service.update_segment_accessibility(1, force=True)

    # Should return OPEN (overwriting manual override due to force=True and no incidents)
    assert result == "OPEN"
    # Verify that calculate_segment_accessibility WAS called
    service.calculate_segment_accessibility.assert_called_once_with(1)
    # Verify that an update was executed
    assert db_session.execute.call_count == 2  # First call (check) + second call (update)
    # Verify that commit was called
    assert db_session.commit.called