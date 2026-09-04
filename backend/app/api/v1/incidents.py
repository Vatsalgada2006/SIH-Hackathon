from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from app.db.session import get_db
from app.db.models import User
from app.services.incident_service import IncidentService
from app.schemas.incident import IncidentCreate, IncidentUpdate, IncidentVerify, IncidentResolve, IncidentResponse
from app.core.security import get_current_active_user, get_current_user_with_role

router = APIRouter()

# Dependency to get incident service
def get_incident_service(db: AsyncSession = Depends(get_db)):
    return IncidentService(db)

# Helper function to convert incident to response with geojson
async def incident_to_response(incident, db: AsyncSession) -> IncidentResponse:
    # We need to get the geometry as GeoJSON
    from geoalchemy2.functions import ST_AsGeoJSON
    from sqlalchemy import select

    result = await db.execute(
        select(ST_AsGeoJSON(incident.geom)).where(incident.id == incident.id)
    )
    geojson = result.scalar_one_or_none()

    return IncidentResponse(
        id=incident.id,
        reporter_id=incident.reporter_id,
        description=incident.description,
        incident_type=incident.incident_type,
        severity=incident.severity,
        latitude=incident.latitude,
        longitude=incident.longitude,
        segment_id=incident.segment_id,
        reported_at=incident.reported_at,
        verified_at=incident.verified_at,
        verified_by=incident.verified_by,
        resolved_at=incident.resolved_at,
        status=incident.status,
        geojson=geojson,
    )

@router.post("/", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(
    incident_in: IncidentCreate,
    current_user: User = Depends(get_current_active_user),
    service: IncidentService = Depends(get_incident_service),
    db: AsyncSession = Depends(get_db),
):
    # If reporter_id is not provided, use the current user's id
    reporter_id = incident_in.reporter_id or current_user.id

    incident = await service.create_incident(
        reporter_id=reporter_id,
        description=incident_in.description,
        incident_type=incident_in.incident_type,
        severity=incident_in.severity,
        latitude=incident_in.latitude,
        longitude=incident_in.longitude,
        segment_id=incident_in.segment_id,
    )

    return await incident_to_response(incident, db)

@router.get("/", response_model=List[IncidentResponse])
async def list_incidents(
    skip: int = Query(0, description="Number of incidents to skip"),
    limit: int = Query(100, description="Maximum number of incidents to return"),
    incident_type: Optional[str] = Query(None, description="Filter by incident type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: User = Depends(get_current_active_user),
    service: IncidentService = Depends(get_incident_service),
    db: AsyncSession = Depends(get_db),
):
    incidents = await service.get_incidents(
        skip=skip,
        limit=limit,
        incident_type=incident_type,
        status=status,
    )

    # Convert each incident to response
    return [await incident_to_response(incident, db) for incident in incidents]

@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: int,
    current_user: User = Depends(get_current_active_user),
    service: IncidentService = Depends(get_incident_service),
    db: AsyncSession = Depends(get_db),
):
    incident = await service.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    return await incident_to_response(incident, db)

@router.patch("/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: int,
    incident_in: IncidentUpdate,
    current_user: User = Depends(get_current_active_user),
    service: IncidentService = Depends(get_incident_service),
    db: AsyncSession = Depends(get_db),
):
    incident = await service.update_incident(
        incident_id=incident_id,
        reporter_id=incident_in.reporter_id,
        description=incident_in.description,
        incident_type=incident_in.incident_type,
        severity=incident_in.severity,
        latitude=incident_in.latitude,
        longitude=incident_in.longitude,
        segment_id=incident_in.segment_id,
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    return await incident_to_response(incident, db)

@router.post("/{incident_id}/verify", response_model=IncidentResponse)
async def verify_incident(
    incident_id: int,
    verify_in: IncidentVerify,
    current_user: User = Depends(get_current_user_with_role(["CONTROL_ROOM", "ADMIN"])),
    service: IncidentService = Depends(get_incident_service),
    db: AsyncSession = Depends(get_db),
):
    incident = await service.verify_incident(
        incident_id=incident_id,
        verified_by=verify_in.verified_by,
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    return await incident_to_response(incident, db)

@router.post("/{incident_id}/resolve", response_model=IncidentResponse)
async def resolve_incident(
    incident_id: int,
    current_user: User = Depends(get_current_user_with_role(["CONTROL_ROOM", "ADMIN"])),
    service: IncidentService = Depends(get_incident_service),
    db: AsyncSession = Depends(get_db),
):
    incident = await service.resolve_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    return await incident_to_response(incident, db)