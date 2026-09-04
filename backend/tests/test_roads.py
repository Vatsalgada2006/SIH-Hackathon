import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User, RoadSegment
from app.db.models.incident import IncidentStatus
from app.schemas.segment import SegmentStatusUpdate
from app.db.session import get_db
from app.core.security import get_current_user, get_current_user_with_role, get_current_active_user
from unittest.mock import MagicMock, AsyncMock, PropertyMock

@pytest.mark.asyncio
async def test_update_segment_status_success(db_session: AsyncSession):
    # Create a user with ADMIN role
    user = User(
        id=1,
        username="admin",
        email="admin@example.com",
        password_hash="hashed",
        role="ADMIN",
        is_active=True
    )
    db_session.add(user)
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

    # Import the app and override dependencies
    from app.main import app
    from fastapi.testclient import TestClient

    # Override the get_db dependency
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Override the get_current_active_user dependency to return our user
    async def override_get_current_active_user():
        return user

    app.dependency_overrides[get_current_active_user] = override_get_current_active_user

    # Keep track of execute call count
    call_count = 0

    # Define what to return for each call
    def execute_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            # First call: get current status for validation (line 114-116)
            result = MagicMock()
            result.scalar_one_or_none.return_value = "UNKNOWN"
            return result
        elif call_count == 2:
            # Second call: get current status inside manually_update_segment_status (line 145-147)
            result = MagicMock()
            result.scalar_one_or_none.return_value = "UNKNOWN"
            return result
        elif call_count == 3:
            # Third call: update segment with manual override (line 154-164)
            return MagicMock()  # Update result
        elif call_count >= 4:
            # Fourth call and beyond: get updated segment to return (lines 133-143)
            result = MagicMock()
            mock_segment_row = MagicMock()
            # Configure the mock to return actual values when attributes are accessed
            type(mock_segment_row).id = PropertyMock(return_value=1)
            type(mock_segment_row).start_node_id = PropertyMock(return_value=1)
            type(mock_segment_row).end_node_id = PropertyMock(return_value=2)
            type(mock_segment_row).length = PropertyMock(return_value=100.0)
            type(mock_segment_row).name = PropertyMock(return_value="Test Segment")
            type(mock_segment_row).status = PropertyMock(return_value="BLOCKED")
            type(mock_segment_row).geojson = PropertyMock(return_value='{"type": "LineString", "coordinates": [[0, 0], [1, 1]]}')
            result.one_or_none.return_value = mock_segment_row
            return result

        # Default return
        return MagicMock()
    
    db_session.execute.side_effect = execute_side_effect
    db_session.commit = AsyncMock()
    db_session.add = MagicMock()
    db_session.refresh = AsyncMock()

    with TestClient(app) as client:
        response = client.patch(
            "/api/v1/roads/segments/1/status",
            json={"status": "BLOCKED", "reason": "Test reason"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "BLOCKED"
        assert data["id"] == 1

    # Clean up overrides
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_segment_status_unauthorized(db_session: AsyncSession):
    # Create a user with DRIVER role (not allowed)
    user = User(
        id=1,
        username="driver",
        email="driver@example.com",
        password_hash="hashed",
        role="DRIVER",
        is_active=True
    )
    db_session.add(user)
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

    # Import the app and override dependencies
    from app.main import app
    from fastapi.testclient import TestClient

    # Override the get_db dependency
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Override the get_current_active_user dependency to return our user
    async def override_get_current_active_user():
        return user

    app.dependency_overrides[get_current_active_user] = override_get_current_active_user

    # Keep track of execute call count
    call_count = 0
    
    # Define what to return for each call
    def execute_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        
        if call_count == 1:
            # First call: get current status for validation (line 114-116)
            result = MagicMock()
            result.scalar_one_or_none.return_value = "UNKNOWN"
            return result
        elif call_count == 2:
            # Second call: get current status inside manually_update_segment_status (line 145-147)
            # This won't be reached because we should get 403 first
            result = MagicMock()
            result.scalar_one_or_none.return_value = "UNKNOWN"
            return result
        elif call_count >= 3:
            # Subsequent calls: get segment to return (lines 133-143)
            # This also won't be reached due to 403
            result = MagicMock()
            mock_segment_row = MagicMock()
            # Configure the mock to return actual values when attributes are accessed
            type(mock_segment_row).id = PropertyMock(return_value=1)
            type(mock_segment_row).start_node_id = PropertyMock(return_value=1)
            type(mock_segment_row).end_node_id = PropertyMock(return_value=2)
            type(mock_segment_row).length = PropertyMock(return_value=100.0)
            type(mock_segment_row).name = PropertyMock(return_value="Test Segment")
            type(mock_segment_row).status = PropertyMock(return_value="UNKNOWN")
            type(mock_segment_row).geojson = PropertyMock(return_value='{"type": "LineString", "coordinates": [[0, 0], [1, 1]]}')
            result.one_or_none.return_value = mock_segment_row
            return result
        
        # Default return
        return MagicMock()
    
    db_session.execute.side_effect = execute_side_effect
    db_session.commit = AsyncMock()
    db_session.add = MagicMock()
    db_session.refresh = AsyncMock()

    with TestClient(app) as client:
        response = client.patch(
            "/api/v1/roads/segments/1/status",
            json={"status": "BLOCKED", "reason": "Test reason"}
        )
        # Should be forbidden
        assert response.status_code == 403

    # Clean up overrides
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_segment_status_invalid_status(db_session: AsyncSession):
    # Create a user with ADMIN role
    user = User(
        id=1,
        username="admin",
        email="admin@example.com",
        password_hash="hashed",
        role="ADMIN",
        is_active=True
    )
    db_session.add(user)
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

    # Import the app and override dependencies
    from app.main import app
    from fastapi.testclient import TestClient

    # Override the get_db dependency
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Override the get_current_active_user dependency to return our user
    async def override_get_current_active_user():
        return user

    app.dependency_overrides[get_current_active_user] = override_get_current_active_user

    # Keep track of execute call count
    call_count = 0
    
    # Define what to return for each call
    def execute_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        
        if call_count == 1:
            # First call: get current status for validation (line 114-116)
            result = MagicMock()
            result.scalar_one_or_none.return_value = "UNKNOWN"
            return result
        elif call_count >= 2:
            # Additional calls shouldn't happen for invalid status
            result = MagicMock()
            result.scalar_one_or_none.return_value = "UNKNOWN"
            return result
        
        # Default return
        return MagicMock()
    
    db_session.execute.side_effect = execute_side_effect
    db_session.commit = AsyncMock()
    db_session.add = MagicMock()
    db_session.refresh = AsyncMock()

    with TestClient(app) as client:
        response = client.patch(
            "/api/v1/roads/segments/1/status",
            json={"status": "INVALID", "reason": "Test reason"}
        )
        # Should be bad request
        assert response.status_code == 400

    # Clean up overrides
    app.dependency_overrides.clear()

