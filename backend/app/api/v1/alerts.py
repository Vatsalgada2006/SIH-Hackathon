from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, or_
from typing import List, Optional
from pydantic import BaseModel
from app.db.session import get_db
from app.db.models import User
from app.db.models import Incident, WeatherSnapshot, RoadSegment
from app.db.models.incident import IncidentStatus, IncidentSeverity
from app.core.security import get_current_active_user
from geoalchemy2.functions import ST_Y, ST_X, ST_Centroid

router = APIRouter()

class AlertResponse(BaseModel):
    id: int
    severity: str  # e.g., LOW, MEDIUM, HIGH, CRITICAL or equivalent for weather
    location: dict  # lat, lon
    time: str  # ISO timestamp
    description: str

    class Config:
        orm_mode = True

@router.get("/", response_model=List[AlertResponse])
async def get_alerts(
    limit: int = Query(50, description="Maximum number of alerts to return"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    alerts = []
    
    # Get active incidents (VERIFIED and not resolved) that are severe
    incident_query = (
        select(Incident)
        .where(
            Incident.status == IncidentStatus.VERIFIED.value,
            Incident.resolved_at.is_(None),
            Incident.severity.in_([IncidentSeverity.HIGH.value, IncidentSeverity.CRITICAL.value])
        )
        .order_by(desc(Incident.reported_at))
        .limit(limit)
    )
    
    incident_result = await db.execute(incident_query)
    incidents = incident_result.scalars().all()
    
    # Format incident alerts
    for incident in incidents:
        # We need to get the lat/lon from the geometry
        lat_result = await db.execute(
            select(ST_Y(Incident.geom)).where(Incident.id == incident.id)
        )
        lat = lat_result.scalar_one_or_none()
        
        lon_result = await db.execute(
            select(ST_X(Incident.geom)).where(Incident.id == incident.id)
        )
        lon = lon_result.scalar_one_or_none()
        
        if lat is not None and lon is not None:
            alerts.append(AlertResponse(
                id=incident.id,
                severity=incident.severity,
                location={"lat": lat, "lon": lon},
                time=incident.reported_at.isoformat() if incident.reported_at else "",
                description=incident.description
            ))
    
    # Get weather alerts - conditions that might affect travel
    # For example: heavy rainfall (>20mm), high wind (>50 km/h), extreme temperature
    weather_query = (
        select(WeatherSnapshot)
        .where(
            or_(
                WeatherSnapshot.rainfall > 20.0,  # Heavy rain
                WeatherSnapshot.wind_speed > 50.0,  # High wind
                WeatherSnapshot.temperature > 40.0,  # Extreme heat
                WeatherSnapshot.temperature < -10.0   # Extreme cold
            )
        )
        .order_by(desc(WeatherSnapshot.recorded_at))
        .limit(limit)
    )
    
    weather_result = await db.execute(weather_query)
    weather_snapshots = weather_result.scalars().all()
    
    # Format weather alerts
    for weather in weather_snapshots:
        # We need to get the lat/lon from the geometry - but weather snapshots 
        # are associated with segments, so we need to get the segment's location
        if weather.segment_id:
            # Get the segment's centroid or a representative point
            lat_result = await db.execute(
                select(ST_Y(ST_Centroid(RoadSegment.geom))).where(RoadSegment.id == weather.segment_id)
            )
            lat = lat_result.scalar_one_or_none()
            
            lon_result = await db.execute(
                select(ST_X(ST_Centroid(RoadSegment.geom))).where(RoadSegment.id == weather.segment_id)
            )
            lon = lon_result.scalar_one_or_none()
        else:
            # If no segment ID, use a default location (center of NE India)
            lat = 26.5
            lon = 93.5
        
        # Determine severity based on weather conditions
        severity = "LOW"
        if weather.rainfall > 50.0 or weather.wind_speed > 80.0:
            severity = "CRITICAL"
        elif weather.rainfall > 20.0 or weather.wind_speed > 50.0 or abs(weather.temperature) > 35.0:
            severity = "HIGH"
        elif weather.rainfall > 10.0 or weather.wind_speed > 25.0:
            severity = "MEDIUM"
        
        # Build description
        description_parts = []
        if weather.rainfall > 20.0:
            description_parts.append(f"Heavy rainfall: {weather.rainfall}mm")
        if weather.wind_speed > 50.0:
            description_parts.append(f"High wind speed: {weather.wind_speed}km/h")
        if weather.temperature > 40.0:
            description_parts.append(f"Extreme heat: {weather.temperature}°C")
        if weather.temperature < -10.0:
            description_parts.append(f"Extreme cold: {weather.temperature}°C")
        
        description = "; ".join(description_parts) if description_parts else "Weather advisory"
        
        if lat is not None and lon is not None:
            alerts.append(AlertResponse(
                id=weather.id,
                severity=severity,
                location={"lat": lat, "lon": lon},
                time=weather.recorded_at.isoformat() if weather.recorded_at else "",
                description=description
            ))
    
    # Sort by time (most recent first) and limit
    alerts.sort(key=lambda x: x.time, reverse=True)
    return alerts[:limit]
