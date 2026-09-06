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
from app.api.v1.districts import router as districts_router
from app.api.v1.risk import router as risk_router
from app.api.v1.vehicles import router as vehicles_router
from app.api.v1.alerts import router as alerts_router
from app.api.v1.routes import router as routes_router
from app.api.v1.auth import router as auth_router
from app.api.v1.roads import router as roads_router
from app.api.v1.incidents import router as incidents_router
from app.api.v1.routing import router as routing_router
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(roads_router, prefix="/api/v1/roads", tags=["roads"])
app.include_router(incidents_router, prefix="/api/v1/incidents", tags=["incidents"])
app.include_router(routing_router, prefix="/api/v1/routing", tags=["routing"])
app.include_router(districts_router, prefix="/api/v1/districts", tags=["districts"])
app.include_router(risk_router, prefix="/api/v1/risk", tags=["risk"])
app.include_router(vehicles_router, prefix="/api/v1/vehicles", tags=["vehicles"])
app.include_router(alerts_router, prefix="/api/v1/alerts", tags=["alerts"])
app.include_router(routes_router, prefix="/api/v1/routes", tags=["routes"])
