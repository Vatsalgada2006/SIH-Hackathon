from fastapi import FastAPI, Depends
from app.core.config import settings
import asyncio
import asyncpg
import aioredis
from typing import Dict

app = FastAPI(
    title="NER Smart Logistics Backend",
    description="Backend for AI-Based Smart Logistics and Accessibility Intelligence Platform for NER",
    version="0.1.0",
)

# Dependency to get settings
def get_settings():
    return settings

# Health check endpoints
@app.get("/health", tags=["health"])
async def health_check() -> Dict[str, str]:
    return {"status": "ok"}

@app.get("/health/db", tags=["health"])
async def health_check_db() -> Dict[str, str]:
    try:
        # Try to connect to the database
        conn = await asyncpg.connect(settings.DATABASE_URL)
        await conn.close()
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}

@app.get("/health/redis", tags=["health"])
async def health_check_redis() -> Dict[str, str]:
    try:
        # Try to connect to Redis
        redis = await aioredis.from_url(settings.REDIS_URL)
        await redis.ping()
        await redis.close()
        return {"status": "ok", "redis": "connected"}
    except Exception as e:
        return {"status": "error", "redis": str(e)}

# Include API routers
from app.api.v1.auth import router as auth_router
from app.api.v1.roads import router as roads_router
from app.api.v1.incidents import router as incidents_router
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(roads_router, prefix="/api/v1/roads", tags=["roads"])
app.include_router(incidents_router, prefix="/api/v1/incidents", tags=["incidents"])
