from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from typing import List, Optional
from pydantic import BaseModel
from app.db.session import get_db
from app.db.models import User
from app.db.models import RoadSegment, Incident, WeatherSnapshot
from app.db.models.incident import IncidentStatus, IncidentSeverity
from app.core.security import get_current_active_user
import json
from datetime import datetime, timedelta

router = APIRouter()

class RiskResponse(BaseModel):
    id: int
    roadId: int
    level: str  # low, medium, high, critical
    cause: str
    predictedAt: Optional[str] = None  # ISO timestamp

    class Config:
        orm_mode = True

@router.get("/", response_model=List[RiskResponse])
async def get_risk_assessment(
    limit: int = Query(100, description="Maximum number of segments to return"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Get road segments
    segments_query = select(RoadSegment.id, RoadSegment.name).limit(limit)
    segments_result = await db.execute(segments_query)
    segments = segments_result.all()
    
    risk_assessments = []
    
    for segment in segments:
        segment_id, segment_name = segment
        
        # Calculate risk based on incidents in the last 24 hours
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        
        # Count active verified incidents (not resolved) in the last 24 hours
        incident_query = (
            select(func.count(Incident.id))
            .where(
                Incident.segment_id == segment_id,
                Incident.status == IncidentStatus.VERIFIED.value,
                Incident.resolved_at.is_(None),
                Incident.reported_at >= twenty_four_hours_ago
            )
        )
        incident_result = await db.execute(incident_query)
        recent_incident_count = incident_result.scalar_one()
        
        # Get severity breakdown for more detailed risk assessment
        severity_query = (
            select(Incident.severity, func.count(Incident.id))
            .where(
                Incident.segment_id == segment_id,
                Incident.status == IncidentStatus.VERIFIED.value,
                Incident.resolved_at.is_(None),
                Incident.reported_at >= twenty_four_hours_ago
            )
            .group_by(Incident.severity)
        )
        severity_result = await db.execute(severity_query)
        severity_counts = dict(severity_result.all())
        
        # Calculate risk based on weather
        # Get the latest weather snapshot for this segment
        weather_query = (
            select(WeatherSnapshot)
            .where(WeatherSnapshot.segment_id == segment_id)
            .order_by(desc(WeatherSnapshot.recorded_at))
            .limit(1)
        )
        weather_result = await db.execute(weather_query)
        latest_weather = weather_result.scalar_one_or_none()
        
        # Determine risk level and cause
        risk_level = "low"
        cause = "normal conditions"
        
        # Check for critical weather conditions
        if latest_weather:
            if latest_weather.rainfall > 50.0:  # Very heavy rainfall
                risk_level = "critical"
                cause = f"extreme rainfall ({latest_weather.rainfall}mm)"
            elif latest_weather.wind_speed > 80.0:  # Extreme wind
                risk_level = "critical"
                cause = f"extreme wind speed ({latest_weather.wind_speed}km/h)"
            elif latest_weather.temperature > 45.0 or latest_weather.temperature < -15.0:  # Extreme temperature
                risk_level = "high"
                cause = f"extreme temperature ({latest_weather.temperature}°C)"
            elif latest_weather.rainfall > 20.0:  # Heavy rainfall
                if risk_level == "low":
                    risk_level = "medium"
                cause = f"heavy rainfall ({latest_weather.rainfall}mm)"
            elif latest_weather.wind_speed > 50.0:  # Strong wind
                if risk_level == "low":
                    risk_level = "medium"
                cause = f"strong wind ({latest_weather.wind_speed}km/h)"
        
        # Check for incidents
        if recent_incident_count > 0:
            # Weight incidents by severity
            incident_risk_score = 0
            incident_risk_score += severity_counts.get(IncidentSeverity.HIGH.value, 0) * 2
            incident_risk_score += severity_counts.get(IncidentSeverity.CRITICAL.value, 0) * 3
            
            if incident_risk_score >= 5:
                risk_level = "critical"
                cause = f"multiple critical incidents ({recent_incident_count} active)"
            elif incident_risk_score >= 3:
                if risk_level in ["low", "medium"]:
                    risk_level = "high"
                cause = f"multiple high severity incidents ({recent_incident_count} active)"
            elif incident_risk_score >= 1:
                if risk_level == "low":
                    risk_level = "medium"
                cause = f"active incidents ({recent_incident_count})"
        
        # If we still have low risk but no specific cause, set a default
        if risk_level == "low" and cause == "normal conditions":
            cause = "normal conditions"
        
        # Predicted at timestamp (when this assessment was made)
        predicted_at = datetime.utcnow().isoformat()
        
        risk_assessments.append(RiskResponse(
            id=segment_id,
            roadId=segment_id,  # In this implementation, roadId is the same as segment ID
            level=risk_level,
            cause=cause,
            predictedAt=predicted_at
        ))
    
    return risk_assessments
