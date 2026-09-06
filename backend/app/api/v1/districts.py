from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from pydantic import BaseModel
from app.db.session import get_db
from app.db.models import RoadSegment, Incident, WeatherSnapshot
from app.db.models.incident import IncidentStatus, IncidentSeverity
from app.core.security import get_current_active_user

router = APIRouter()

class DistrictRisk(BaseModel):
    id: str
    name: str
    risk_level: str  # LOW, MEDIUM, HIGH
    incident_count: int
    active_incidents: int
    description: str

    class Config:
        orm_mode = True

@router.get("/", response_model=List[DistrictRisk])
async def get_districts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Get all segments to determine the geographical bounds
    bounds_query = (
        select(
            func.min(func.ST_X(RoadSegment.geom)).label("min_lon"),
            func.max(func.ST_X(RoadSegment.geom)).label("max_lon"),
            func.min(func.ST_Y(RoadSegment.geom)).label("min_lat"),
            func.max(func.ST_Y(RoadSegment.geom)).label("max_lat")
        )
    )
    bounds_result = await db.execute(bounds_query)
    bounds = bounds_result.one()
    
    min_lon, max_lon, min_lat, max_lat = bounds
    
    # If we don't have any segments, return mock data
    if min_lon is None or max_lon is None or min_lat is None or max_lat is None:
        # Return some mock districts
        return [
            DistrictRisk(
                id="district_1",
                name="Northern District",
                risk_level="LOW",
                incident_count=2,
                active_incidents=0,
                description="Covers the northern region of the map"
            ),
            DistrictRisk(
                id="district_2",
                name="Central District",
                risk_level="MEDIUM",
                incident_count=5,
                active_incidents=2,
                description="Covers the central urban area"
            ),
            DistrictRisk(
                id="district_3",
                name="Southern District",
                risk_level="HIGH",
                incident_count=8,
                active_incidents=3,
                description="Covers the southern mountainous region"
            )
        ]
    
    # Divide the area into a 3x3 grid for simplicity
    # We'll create 9 districts
    districts = []
    
    lon_step = (max_lon - min_lon) / 3
    lat_step = (max_lat - min_lat) / 3
    
    for i in range(3):
        for j in range(3):
            # Calculate the bounds for this district
            district_min_lon = min_lon + i * lon_step
            district_max_lon = min_lon + (i + 1) * lon_step
            district_min_lat = min_lat + j * lat_step
            district_max_lat = min_lat + (j + 1) * lat_step
            
            # Create a polygon for this district
            from geoalchemy2.functions import ST_MakeEnvelope
            polygon = func.ST_MakeEnvelope(
                district_min_lon, district_min_lat,
                district_max_lon, district_max_lat,
                4326
            )
            
            # Count segments in this district
            segment_query = (
                select(func.count(RoadSegment.id))
                .where(func.ST_Intersects(RoadSegment.geom, polygon))
            )
            segment_result = await db.execute(segment_query)
            segment_count = segment_result.scalar_one()
            
            # Count incidents in this district (active verified incidents)
            incident_query = (
                select(func.count(Incident.id))
                .where(
                    func.ST_Intersects(Incident.geom, polygon),
                    Incident.status == IncidentStatus.VERIFIED.value,
                    Incident.resolved_at.is_(None)
                )
            )
            incident_result = await db.execute(incident_query)
            incident_count = incident_result.scalar_one()
            
            # Determine risk level based on incident count
            if incident_count == 0:
                risk_level = "LOW"
            elif incident_count <= 2:
                risk_level = "MEDIUM"
            else:
                risk_level = "HIGH"
            
            districts.append(DistrictRisk(
                id=f"district_{i}_{j}",
                name=f"District {i+1}-{j+1}",
                risk_level=risk_level,
                incident_count=incident_count,
                active_incidents=incident_count,  # Simplified
                description=f"Covering area from ({district_min_lon:.3f},{district_min_lat:.3f}) to ({district_max_lon:.3f},{district_max_lat:.3f})"
            ))
    
    return districts
