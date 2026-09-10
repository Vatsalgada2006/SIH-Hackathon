from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from urllib.parse import urlparse, parse_qs

# Parse the DATABASE_URL to extract SSL parameters
url = settings.DATABASE_URL
parsed = urlparse(url)

# Get the query parameters
query_params = parse_qs(parsed.query)

# Remove the query parameters from the URL
base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
if parsed.fragment:
    base_url += f"#{parsed.fragment}"

# Extract SSL parameters
connect_args = {}
if 'sslmode' in query_params:
    # Map sslmode values to what asyncpg expects
    sslmode_map = {
        'require': True,
        'verify-ca': True,
        'verify-full': True,
        'disable': False,
        'allow': False,
        'prefer': False
    }
    sslmode_value = query_params['sslmode'][0]
    connect_args['ssl'] = sslmode_map.get(sslmode_value, True)
if 'channel_binding' in query_params:
    # channel_binding might need special handling
    # For now, we'll ignore it as asyncpg may handle it differently
    pass

# Create async engine
engine = create_async_engine(
    base_url,
    echo=False,  # Set to True for SQL logging
    future=True,
    connect_args=connect_args
)

# Create async session factory
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# Dependency to get DB session
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session