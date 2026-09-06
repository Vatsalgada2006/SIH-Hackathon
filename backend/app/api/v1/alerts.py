from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
from typing import List, Optional
from pydantic import BaseModel
from app.db.session import get_db
from app.db.models import User
from app.db.models import Incident, WeatherSnapshot
from app.db.models.incident import IncidentStatus, IncidentSeverity
from app.core.security import get_current_active_user

router = APIRouter()

class IncidentAlert(BaseModel):
    id: int
    type: str  # e.g., "LANDSLIDE", "FLOOD"
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    description: str
    location: dict  # lat, lon
    reported_at: str
    verified_at: Optional[str]
    status: str

    class Config:
        orm_mode = True

class WeatherAlert(BaseModel):
    id: int
    segment_id: Optional[int]
    rainfall: float  # mm
    temperature: float  # celsius
    wind_speed: float  # km/h
    humidity: float  # percentage
    recorded_at: str
    alert_type: str  # e.g., "HEAVY_RAIN", "HIGH_WIND"
    description: str

    class Config:
        orm_mode = True

class AlertsResponse(BaseModel):
    incidents: List[IncidentAlert]
    weather: List[WeatherAlert]

@router.get("/", response_model=AlertsResponse)
async def get_alerts(
    limit: int = Query(50, description="Maximum number of alerts to return per type"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
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
    incident_alerts = []
    for incident in incidents:
        # We need to get the lat/lon from the geometry
        from geoalchemy2.functions import ST_Y, ST_X
        lat_result = await db.execute(
            select(ST_Y(Incident.geom)).where(Incident.id == incident.id)
        )
        lat = lat_result.scalar_one_or_none()
        
        lon_result = await db.execute(
            select(ST_X(Incident.geom)).where(Incident.id == incident.id)
        )
        lon = lon_result.scalar_one_or_none()
        
        incident_alerts.append(IncidentAlert(
            id=incident.id,
            type=incident.incident_type,
            severity=incident.severity,
            description=incident.description,
            location={"lat": lat, "lon": lon},
            reported_at=incident.reported_at.isoformat() if incident.reported_at else None,
            verified_at=incident.verified_at.isoformat() if incident.verified_at else None,
            status=incident.status
        ))
    
    # Get weather alerts - conditions that might affect travel
    # For example: heavy rainfall (>20mm), high wind (>50 km/h), extreme temperature
    weather_query = (
        select(WeatherSnapshot)
        .where(
            (WeatherSnapshot.rainfall > 20.0) |  # Heavy rain
            (WeatherSnapshot.wind_speed > 50.0) |  # High wind
            (WeatherSnapshot.temperature > 40.0) |  # Extreme heat
            (WeatherSnapshot.temperature < -10.0)  # Extreme cold
        )
        .order_by(desc(WeatherSnapshot.recorded_at))
        .limit(limit)
    )
    
    weather_result = await db.execute(weather_query)
    weather_snapshots = weather_result.scalars().all()
    
    # Format weather alerts
    weather_alerts = []
    for weather in weather_snapshots:
        alert_type = []
        description_parts = []
        
        if weather.rainfall > 20.0:
            alert_type.append("HEAVY_RAIN")
            description_parts.append(f"Heavy rainfall: {weather.rainfall}mm")
        
        if weather.wind_speed > 50.0:
            alert_type.append("HIGH_WIND")
            description_parts.append(f"High wind speed: {weather.wind_speed}km/h")
        
        if weather.temperature > 40.0:
            alert_type.append("EXTREME_HEAT")
            description_parts.append(f"Extreme temperature: {weather.temperature}°C")
        
        if weather.temperature < -10.0:
            alert_type.append("EXTREME_COLD")
            description_parts.append(f"Extreme temperature: {weather.temperature}°C")
        
        alert_type_str = "_".join(alert_type) if alert_type else "WEATHER_ADVISORY"
        description = "; ".join(description_parts) if description_parts else "Weather conditions normal"
        
        weather_alerts.append(WeatherAlert(
            id=weather.id,
            segment_id=weather.segment_id,
            rainfall=weather.rainfall,
            temperature=weather.temperature,
            wind_speed=weather.wind_speed,
            humidity=weather.humidity,
            recorded_at=weather.recorded_at.isoformat() if weather.recorded_at else None,
            alert_type=alert_type_str,
            description=description
        ))
    
    return AlertsResponse(
        incidents=incident_alerts,
        weather=weather_alerts
    )
