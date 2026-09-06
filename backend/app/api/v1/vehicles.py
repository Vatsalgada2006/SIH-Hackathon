from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from pydantic import BaseModel
from app.db.session import get_db
from app.db.models import Vehicle, VehiclePosition
from app.core.security import get_current_active_user

router = APIRouter()

class VehicleResponse(BaseModel):
    id: int
    vehicle_id: str
    type: str
    capacity: Optional[float]
    current_segment_id: Optional[int]
    last_position: Optional[dict]  # Will contain lat, lon, speed, timestamp
    status: str  # e.g., active, idle, maintenance

    class Config:
        orm_mode = True

@router.get("/", response_model=List[VehicleResponse])
async def get_vehicles(
    skip: int = Query(0, description="Number of vehicles to skip"),
    limit: int = Query(100, description="Maximum number of vehicles to return"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Get vehicles with their latest position
    query = (
        select(Vehicle)
        .offset(skip)
        .limit(limit)
    )
    
    result = await db.execute(query)
    vehicles = result.scalars().all()
    
    # For each vehicle, get the latest position
    vehicle_responses = []
    for vehicle in vehicles:
        # Get the latest position for this vehicle
        position_result = await db.execute(
            select(VehiclePosition)
            .where(VehiclePosition.vehicle_id == vehicle.id)
            .order_by(desc(VehiclePosition.recorded_at))
            .limit(1)
        )
        latest_position = position_result.scalar_one_or_none()
        
        # Format the position data
        position_data = None
        if latest_position:
            # We need to get the lat/lon from the geometry
            from geoalchemy2.functions import ST_AsText, ST_Y, ST_X
            lat_result = await db.execute(
                select(ST_Y(VehiclePosition.geom)).where(VehiclePosition.id == latest_position.id)
            )
            lat = lat_result.scalar_one_or_none()
            
            lon_result = await db.execute(
                select(ST_X(VehiclePosition.geom)).where(VehiclePosition.id == latest_position.id)
            )
            lon = lon_result.scalar_one_or_none()
            
            position_data = {
                "lat": lat,
                "lon": lon,
                "speed": latest_position.speed,
                "timestamp": latest_position.recorded_at.isoformat() if latest_position.recorded_at else None
            }
        
        # Determine vehicle status based on speed or other factors
        status = "active"  # default
        if latest_position:
            if latest_position.speed < 1.0:
                status = "idle"
            elif latest_position.speed > 80.0:  # assuming speed limit
                status = "overspeeding"
        
        vehicle_responses.append(VehicleResponse(
            id=vehicle.id,
            vehicle_id=vehicle.vehicle_id,
            type=vehicle.type,
            capacity=vehicle.capacity,
            current_segment_id=vehicle.current_segment_id,
            last_position=position_data,
            status=status
        ))
    
    return vehicle_responses
