import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.accessibility_service import AccessibilityService
from app.db.models import RoadSegment

async def test_manual_override_logic():
    """Test the core manual override logic"""
    print("=== Testing Manual Override Logic ===")
    
    # Setup mock session
    db_session = AsyncMock(spec=AsyncSession)
    
    # Create a mock segment with manual override
    mock_segment = MagicMock(spec=RoadSegment)
    mock_segment.id = 1
    mock_segment.status = "OPEN"
    mock_segment.manual_override = True
    mock_segment.manual_override_reason = "Test override"
    
    # Mock the execute method to return our segment when queried for manual override check
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_segment
    
    # We expect two calls: one for the select in calculate_segment_accessibility
    # and potentially another for update if we call it
    mock_update_result = MagicMock()
    mock_update_result.scalars.return_value.all.return_value = []
    
    db_session.execute.side_effect = [mock_result, mock_update_result]
    db_session.commit = AsyncMock()
    
    service = AccessibilityService(db_session)
    
    # Test 1: calculate_segment_accessibility should respect manual override
    result = await service.calculate_segment_accessibility(1)
    print(f"calculate_segment_accessibility result: {result}")
    assert result == "OPEN", f"Expected OPEN, got {result}"
    print("✓ Manual override respected in calculate_segment_accessibility")
    
    # Test 2: update_segment_accessibility with force=False should respect manual override
    # Reset the mock for this test
    db_session.execute.side_effect = [mock_result, mock_update_result]
    result = await service.update_segment_accessibility(1, force=False)
    print(f"update_segment_accessibility(force=False) result: {result}")
    assert result == "OPEN", f"Expected OPEN (respecting manual override), got {result}"
    print("✓ Manual override respected in update_segment_accessibility with force=False")
    
    # Test 3: update_segment_accessibility with force=True should allow override
    # Reset the mock for this test
    db_session.execute.side_effect = [mock_result, mock_update_result]
    result = await service.update_segment_accessibility(1, force=True)
    print(f"update_segment_accessibility(force=True) result: {result}")
    assert result == "OPEN", f"Expected OPEN (no incidents to change it), got {result}"
    print("✓ Force override works in update_segment_accessibility")
    
    print("\\n🎉 All manual override logic tests PASSED!")

if __name__ == "__main__":
    asyncio.run(test_manual_override_logic())
