from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from pydantic import BaseModel
from app.db.session import get_db
from app.db.models import RoadSegment, Incident, User
from app.db.models.incident import IncidentStatus
from app.core.security import get_current_active_user
from app.services.accessibility_service import AccessibilityService
from geoalchemy2.functions import ST_MakeEnvelope

router = APIRouter()

class DistrictResponse(BaseModel):
    id: str
    name: str
    state: str  # e.g., "Arunachal Pradesh", "Assam", etc.
    status: str  # accessible, at_risk, inaccessible

    class Config:
        orm_mode = True

@router.get("/", response_model=List[DistrictResponse])
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
        # Return some mock districts for NE India states
        return [
            DistrictResponse(
                id="district_1",
                name="Arunachal Pradesh",
                state="Arunachal Pradesh",
                status="accessible"
            ),
            DistrictResponse(
                id="district_2",
                name="Assam",
                state="Assam",
                status="at_risk"
            ),
            DistrictResponse(
                id="district_3",
                name="Manipur",
                state="Manipur",
                status="inaccessible"
            ),
            DistrictResponse(
                id="district_4",
                name="Meghalaya",
                state="Meghalaya",
                status="accessible"
            ),
            DistrictResponse(
                id="district_5",
                name="Mizoram",
                state="Mizoram",
                status="at_risk"
            ),
            DistrictResponse(
                id="district_6",
                name="Nagaland",
                state="Nagaland",
                status="accessible"
            ),
            DistrictResponse(
                id="district_7",
                name="Sikkim",
                state="Sikkim",
                status="accessible"
            ),
            DistrictResponse(
                id="district_8",
                name="Tripura",
                state="Tripura",
                status="at_risk"
            )
        ]
    
    # Divide the area into a grid based on the number of districts we want to return
    # For simplicity, we'll create districts based on a 3x3 grid and assign state names
    districts = []
    
    lon_step = (max_lon - min_lon) / 3
    lat_step = (max_lat - min_lat) / 3
    
    # List of NE India states for naming
    ne_states = [
        "Arunachal Pradesh", "Assam", "Manipur", "Meghalaya", 
        "Mizoram", "Nagaland", "Sikkim", "Tripura"
    ]
    
    state_index = 0
    for i in range(3):
        for j in range(3):
            # Calculate the bounds for this district
            district_min_lon = min_lon + i * lon_step
            district_max_lon = min_lon + (i + 1) * lon_step
            district_min_lat = min_lat + j * lat_step
            district_max_lat = min_lat + (j + 1) * lat_step
            
            # Create a polygon for this district
            polygon = func.ST_MakeEnvelope(
                district_min_lon, district_min_lat,
                district_max_lon, district_max_lat,
                4326
            )
            
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
            
            # Determine status based on incident count
            if incident_count == 0:
                status = "accessible"
            elif incident_count <= 2:
                status = "at_risk"
            else:
                status = "inaccessible"
            
            # Get state name (cycle through the list)
            state_name = ne_states[state_index % len(ne_states)]
            state_index += 1
            
            districts.append(DistrictResponse(
                id=f"district_{i}_{j}",
                name=f"{state_name} Region {i+1}-{j+1}",
                state=state_name,
                status=status
            ))
    
    return districts
