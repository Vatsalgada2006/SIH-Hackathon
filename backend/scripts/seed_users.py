import os
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models import User

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Admin credentials from environment variables with defaults
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

async def seed_admin_user():
    """Seed the database with an initial admin user if it doesn't exist."""
    async with AsyncSessionLocal() as session:
        # Check if admin user already exists
        result = await session.execute(select(User).where(User.username == ADMIN_USERNAME))
        existing_user = result.scalar_one_or_none()

        if existing_user is None:
            # Create new admin user
            hashed_password = pwd_context.hash(ADMIN_PASSWORD)
            admin_user = User(
                username=ADMIN_USERNAME,
                email=f"{ADMIN_USERNAME}@example.com",  # placeholder email
                password_hash=hashed_password,
                role="ADMIN",
                is_active=True
            )
            session.add(admin_user)
            await session.commit()
            print(f"Admin user '{ADMIN_USERNAME}' created successfully.")
        else:
            print(f"Admin user '{ADMIN_USERNAME}' already exists. Skipping creation.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(seed_admin_user())