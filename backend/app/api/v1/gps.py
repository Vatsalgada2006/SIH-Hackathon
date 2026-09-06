from app.db.models import User
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from geoalchemy2.functions import ST_Distance, ST_SetSRID, ST_MakePoint
from app.db.session import get_db
from app.db.models import Vehicle, VehiclePosition, RoadSegment
from app.core.security import get_current_active_user
from app.services.accessibility_service import AccessibilityService
import aioredis
import json
from datetime import datetime
from typing import Optional

router = APIRouter()

# Dependency to get Redis connection
async def get_redis():
    from app.core.config import settings
    redis = await aioredis.from_url(settings.REDIS_URL)
    try:
        yield redis
    finally:
        await redis.close()

# Dependency to get accessibility service
def get_accessibility_service(db: AsyncSession = Depends(get_db)):
    return AccessibilityService(db)

@router.post("/", status_code=status.HTTP_201_CREATED)
async def ingest_gps_data(
    gps_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    accessibility_service: AccessibilityService = Depends(get_accessibility_service),
):
    """
    Ingest GPS data from a vehicle.
    Expected format: {
        "vehicle_id": "string",  # e.g., license plate or unique identifier
        "lat": float,           # Latitude
        "lon": float,           # Longitude
        "speed": float,         # Speed in km/h
        "timestamp": "ISO string"  # Optional, defaults to current time
    }
    """
    # Extract data
    vehicle_id_str = gps_data.get("vehicle_id")
    lat = gps_data.get("lat")
    lon = gps_data.get("lon")
    speed = gps_data.get("speed", 0.0)
    timestamp_str = gps_data.get("timestamp")
    
    # Validate required fields
    if not vehicle_id_str or lat is None or lon is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="vehicle_id, lat, and lon are required"
        )
    
    # Parse timestamp if provided, otherwise use current time
    if timestamp_str:
        try:
            recorded_at = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid timestamp format. Use ISO format."
            )
    else:
        recorded_at = datetime.utcnow()
    
    # Find or create the vehicle
    result = await db.execute(
        select(Vehicle).where(Vehicle.vehicle_id == vehicle_id_str)
    )
    vehicle = result.scalar_one_or_none()
    
    if not vehicle:
        # Create a new vehicle if it doesn't exist
        # In a real system, you might want to require registration first
        vehicle = Vehicle(
            vehicle_id=vehicle_id_str,
            type="UNKNOWN",  # Default type
            capacity=None
        )
        db.add(vehicle)
        await db.commit()
        await db.refresh(vehicle)
    
    # Map the GPS point to the nearest road segment
    point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    
    # Query the nearest segment
    result = await db.execute(
        select(RoadSegment.id)
        .order_by(ST_Distance(RoadSegment.geom, point))
        .limit(1)
    )
    nearest_segment_id = result.scalar_one_or_none()
    
    if nearest_segment_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No road segments found"
        )
    
    # Update the vehicle's current segment
    vehicle.current_segment_id = nearest_segment_id
    
    # Store the vehicle position
    position = VehiclePosition(
        vehicle_id=vehicle.id,
        geom=point,
        speed=speed,
        direction=0.0,  # Default direction, could be calculated from previous positions
        recorded_at=recorded_at
    )
    db.add(position)
    
    # Commit the vehicle and position updates
    await db.commit()
    await db.refresh(vehicle)
    await db.refresh(position)
    
    # Update rolling average speed in Redis
    # We'll keep a sliding window of the last N speeds for each segment
    segment_speed_key = f"segment:speed:{nearest_segment_id}"
    
    # Add the new speed to the list (we'll keep the last 10 readings)
    await redis.lpush(segment_speed_key, speed)
    await redis.ltrim(segment_speed_key, 0, 9)  # Keep only last 10
    
    # Get the average speed from the last 10 readings
    speeds = await redis.lrange(segment_speed_key, 0, -1)
    if speeds:
        # Convert from bytes to float
        speeds = [float(s.decode('utf-8')) for s in speeds]
        avg_speed = sum(speeds) / len(speeds)
    else:
        avg_speed = speed
    
    # Determine if we should update accessibility based on speed
    # According to the instructions:
    # - congestion → DEGRADED
    # - near-zero speed sustained → BLOCKED
    
    # We'll consider:
    # - BLOCKED: average speed < 5 km/h for at least 3 consecutive readings
    # - DEGRADED: average speed < 20 km/h (but not blocked)
    # - OPEN: average speed >= 20 km/h
    
    # Check if we have enough readings to make a determination
    if len(speeds) >= 3:
        # Check if all of the last 3 readings are below 5 km/h (near-zero)
        recent_speeds = speeds[:3]  # Most recent 3
        if all(s < 5.0 for s in recent_speeds):
            # Near-zero speed sustained -> BLOCKED
            new_status = "BLOCKED"
        elif avg_speed < 20.0:
            # Congestion but not blocked -> DEGRADED
            new_status = "DEGRADED"
        else:
            # Normal speed -> OPEN
            new_status = "OPEN"
        
        # Update the segment accessibility if it has changed
        # We use force=False to respect manual overrides
        current_status = await accessibility_service.calculate_segment_accessibility(nearest_segment_id)
        if current_status != new_status:
            await accessibility_service.update_segment_accessibility(nearest_segment_id, force=False)
    
    return {
        "status": "success",
        "message": "GPS data ingested successfully",
        "vehicle_id": vehicle.vehicle_id,
        "segment_id": nearest_segment_id,
        "speed": speed,
        "avg_speed": avg_speed if len(speeds) > 0 else None
    }
