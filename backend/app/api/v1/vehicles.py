from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from pydantic import BaseModel
from app.db.session import get_db
from app.db.models import User
from app.db.models import Vehicle, VehiclePosition, RoadSegment
from app.core.security import get_current_active_user
from geoalchemy2.functions import ST_AsGeoJSON, ST_Y, ST_X
import json

router = APIRouter()

class VehicleResponse(BaseModel):
    id: int
    origin: str  # Starting point description or coordinates
    destination: str  # Destination point description or coordinates
    currentLocation: str  # Current location description or coordinates
    coordinates: List[List[float]]  # list of [lat, lon] for the vehicle's current position trace
    commodity: str  # What the vehicle is carrying
    status: str  # e.g., on_route, at_risk, stopped, delayed, delivered
    delayMinutes: int  # Delay in minutes

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
        
        # Format the position data as coordinates [lat, lon]
        coordinates = []
        if latest_position:
            # We need to get the lat/lon from the geometry
            lat_result = await db.execute(
                select(ST_Y(VehiclePosition.geom)).where(VehiclePosition.id == latest_position.id)
            )
            lat = lat_result.scalar_one_or_none()
            
            lon_result = await db.execute(
                select(ST_X(VehiclePosition.geom)).where(VehiclePosition.id == latest_position.id)
            )
            lon = lon_result.scalar_one_or_none()
            
            if lat is not None and lon is not None:
                coordinates = [[lat, lon]]  # Single point as list of [lat, lon]
        
        # Determine origin and destination (simplified - in reality these would come from trip data)
        origin = f"Origin {vehicle.id}"
        destination = f"Destination {vehicle.id}"
        currentLocation = "Unknown"
        
        if latest_position and lat is not None and lon is not None:
            currentLocation = f"{lat:.6f},{lon:.6f}"
        
        # Determine vehicle status based on speed or other factors
        status = "on_route"  # default
        delay_minutes = 0
        commodity = "General Goods"
        
        if latest_position:
            if latest_position.speed < 1.0:
                status = "stopped"
                delay_minutes = 5  # Assume some delay if stopped
            elif latest_position.speed < 10.0:
                status = "delayed"
                delay_minutes = 15
            else:
                status = "on_route"
                delay_minutes = 0
        
        # In a real system, we would check if the current segment has issues
        # For now, we'll simulate based on vehicle ID
        if vehicle.id % 3 == 0:
            status = "at_risk"
        elif vehicle.id % 5 == 0:
            status = "delayed"
            delay_minutes = 10
        
        vehicle_responses.append(VehicleResponse(
            id=vehicle.id,
            origin=origin,
            destination=destination,
            currentLocation=currentLocation,
            coordinates=coordinates,
            commodity=commodity,
            status=status,
            delayMinutes=delay_minutes
        ))
    
    return vehicle_responses
