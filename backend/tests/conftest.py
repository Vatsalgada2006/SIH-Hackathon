import pytest
import pytest_asyncio
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.fixture
def db_session():
    """Return an AsyncMock that simulates a database session."""
    return AsyncMock(spec=AsyncSession)
