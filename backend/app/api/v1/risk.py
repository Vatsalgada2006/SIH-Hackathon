from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import List, Optional
from pydantic import BaseModel
from app.db.session import get_db
from app.db.models import RoadSegment, Incident, WeatherSnapshot
from app.db.models.incident import IncidentStatus, IncidentSeverity
from app.core.security import get_current_active_user

router = APIRouter()

class SegmentRisk(BaseModel):
    id: int
    name: str
    risk_score: float  # 0-100, higher means higher risk
    risk_level: str  # LOW, MEDIUM, HIGH
    factors: dict  # contributing factors

    class Config:
        orm_mode = True

@router.get("/", response_model=List[SegmentRisk])
async def get_risk_assessment(
    limit: int = Query(100, description="Maximum number of segments to return"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Get road segments
    segments_query = select(RoadSegment).limit(limit)
    segments_result = await db.execute(segments_query)
    segments = segments_result.scalars().all()
    
    risk_assessments = []
    
    for segment in segments:
        # Calculate risk based on incidents
        # Count active verified incidents (not resolved) in the last 24 hours
        from datetime import datetime, timedelta
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        
        incident_query = (
            select(func.count(Incident.id))
            .where(
                Incident.segment_id == segment.id,
                Incident.status == IncidentStatus.VERIFIED.value,
                Incident.resolved_at.is_(None),
                Incident.reported_at >= twenty_four_hours_ago
            )
        )
        incident_result = await db.execute(incident_query)
        recent_incident_count = incident_result.scalar_one()
        
        # Weight for incidents: each HIGH severity incident adds 30 points, CRITICAL adds 50
        # We'll get the severity breakdown
        severity_query = (
            select(Incident.severity, func.count(Incident.id))
            .where(
                Incident.segment_id == segment.id,
                Incident.status == IncidentStatus.VERIFIED.value,
                Incident.resolved_at.is_(None),
                Incident.reported_at >= twenty_four_hours_ago
            )
            .group_by(Incident.severity)
        )
        severity_result = await db.execute(severity_query)
        severity_counts = dict(severity_result.all())
        
        incident_risk = 0
        incident_risk += severity_counts.get(IncidentSeverity.HIGH.value, 0) * 30
        incident_risk += severity_counts.get(IncidentSeverity.CRITICAL.value, 0) * 50
        
        # Calculate risk based on weather
        # Get the latest weather snapshot for this segment
        weather_query = (
            select(WeatherSnapshot)
            .where(WeatherSnapshot.segment_id == segment.id)
            .order_by(desc(WeatherSnapshot.recorded_at))
            .limit(1)
        )
        weather_result = await db.execute(weather_query)
        latest_weather = weather_result.scalar_one_or_none()
        
        weather_risk = 0
        weather_factors = {}
        if latest_weather:
            # Heavy rainfall: >10mm adds 20 points, >20mm adds 40 points
            if latest_weather.rainfall > 20.0:
                weather_risk += 40
                weather_factors["heavy_rainfall"] = latest_weather.rainfall
            elif latest_weather.rainfall > 10.0:
                weather_risk += 20
                weather_factors["rainfall"] = latest_weather.rainfall
            
            # High wind: >30km/h adds 20 points, >50km/h adds 40 points
            if latest_weather.wind_speed > 50.0:
                weather_risk += 40
                weather_factors["high_wind"] = latest_weather.wind_speed
            elif latest_weather.wind_speed > 30.0:
                weather_risk += 20
                weather_factors["wind_speed"] = latest_weather.wind_speed
            
            # Extreme temperature: >40°C or < -10°C adds 30 points
            if latest_weather.temperature > 40.0 or latest_weather.temperature < -10.0:
                weather_risk += 30
                weather_factors["extreme_temperature"] = latest_weather.temperature
        
        # Total risk score (capped at 100)
        total_risk = min(incident_risk + weather_risk, 100)
        
        # Determine risk level
        if total_risk >= 70:
            risk_level = "HIGH"
        elif total_risk >= 40:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        risk_assessments.append(SegmentRisk(
            id=segment.id,
            name=segment.name or f"Segment {segment.id}",
            risk_score=float(total_risk),
            risk_level=risk_level,
            factors={
                "incidents": {
                    "count": recent_incident_count,
                    "severity_breakdown": severity_counts
                },
                "weather": weather_factors if latest_weather else None
            }
        ))
    
    return risk_assessments
