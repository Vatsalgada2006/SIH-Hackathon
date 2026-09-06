import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, Mock
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.fixture
def db_session():
    """Return an AsyncMock that simulates a database session."""
    mock = AsyncMock(spec=AsyncSession)
    # Configure the execute method to return a mock result when awaited
    mock_result = Mock()  # Use a regular Mock for the result
    mock_result.scalar_one_or_none.return_value = 999  # default, can be overridden in tests
    mock.execute.return_value = mock_result
    return mock
