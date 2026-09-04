from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from geoalchemy2.functions import ST_MakeEnvelope, ST_Intersects, ST_Distance, ST_AsGeoJSON
from app.db.session import get_db
from app.db.models import RoadSegment, AuditLog, User
from app.schemas.segment import SegmentResponse, SegmentStatusUpdate
from app.services.accessibility_service import AccessibilityService
from app.core.security import get_current_user_with_role

router = APIRouter()

@router.get("/segments", response_model=list[SegmentResponse])
async def get_segments_by_bbox(
    bbox: str = Query(..., description="Bounding box as min_lon,min_lat,max_lon,max_lat"),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, description="Maximum number of segments to return"),
):
    try:
        min_lon, min_lat, max_lon, max_lat = map(float, bbox.split(","))
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid bbox format. Expected min_lon,min_lat,max_lon,max_lat",
        )

    # Create a polygon from the bbox
    polygon = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)

    # Query segments that intersect with the polygon
    query = (
        select(
            RoadSegment.id,
            RoadSegment.start_node_id,
            RoadSegment.end_node_id,
            RoadSegment.length,
            RoadSegment.name,
            RoadSegment.status,
            func.ST_AsGeoJSON(RoadSegment.geom).label("geojson"),
        )
        .where(ST_Intersects(RoadSegment.geom, polygon))
        .limit(limit)
    )

    result = await db.execute(query)
    segments = result.all()

    # Convert to list of dictionaries matching the SegmentResponse model
    return [
        SegmentResponse(
            id=seg.id,
            start_node_id=seg.start_node_id,
            end_node_id=seg.end_node_id,
            length=seg.length,
            name=seg.name,
            status=seg.status,
            geojson=seg.geojson,
        )
        for seg in segments
    ]

@router.get("/segments/nearest", response_model=SegmentResponse)
async def get_nearest_segment(
    lat: float = Query(..., description="Latitude of the point"),
    lon: float = Query(..., description="Longitude of the point"),
    db: AsyncSession = Depends(get_db),
):
    # Create a point from the lat, lon
    point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)

    # Query the nearest segment
    query = (
        select(
            RoadSegment.id,
            RoadSegment.start_node_id,
            RoadSegment.end_node_id,
            RoadSegment.length,
            RoadSegment.name,
            RoadSegment.status,
            func.ST_AsGeoJSON(RoadSegment.geom).label("geojson"),
        )
        .order_by(ST_Distance(RoadSegment.geom, point))
        .limit(1)
    )

    result = await db.execute(query)

    if segment is None:
        raise HTTPException(status_code=404, detail="No segments found")

    return SegmentResponse(
        id=segment.id,
        start_node_id=segment.start_node_id,
        end_node_id=segment.end_node_id,
        length=segment.length,
        name=segment.name,
        status=segment.status,
        geojson=segment.geojson,
    )

@router.patch("/segments/{segment_id}/status", response_model=SegmentResponse)
async def update_segment_status(
    segment_id: int,
    status_update: SegmentStatusUpdate,
    current_user: User = Depends(get_current_user_with_role(["ADMIN", "CONTROL_ROOM"])),
    db: AsyncSession = Depends(get_db),
):
    # Validate the status is allowed (though the schema does it)
    allowed_statuses = ['OPEN', 'DEGRADED', 'BLOCKED', 'UNKNOWN']
    if status_update.status not in allowed_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status_update.status}")

    # Get the current status
    result = await db.execute(
        select(RoadSegment.status).where(RoadSegment.id == segment_id)
    )
    current_status = result.scalar_one_or_none()

    if current_status is None:
        raise HTTPException(status_code=404, detail=f"Segment with id {segment_id} not found")


    # Use accessibility service to manually update segment status (respects manual override logic)
    accessibility_service = AccessibilityService(db)
    new_status = await accessibility_service.manually_update_segment_status(
        segment_id=segment_id,
        new_status=status_update.status,
        user_id=current_user.id,
        reason=status_update.reason
    )

    # Get the updated segment to return
    result = await db.execute(
        select(
            RoadSegment.id,
            RoadSegment.start_node_id,
            RoadSegment.end_node_id,
            RoadSegment.length,
            RoadSegment.name,
            RoadSegment.status,
            func.ST_AsGeoJSON(RoadSegment.geom).label("geojson"),
        )
        .where(RoadSegment.id == segment_id)
    )
    segment = result.one_or_none()

    if segment is None:
        raise HTTPException(status_code=404, detail=f"Segment with id {segment_id} not found after update")
    return SegmentResponse(
        id=segment.id,
        start_node_id=segment.start_node_id,
        end_node_id=segment.end_node_id,
        length=segment.length,
        name=segment.name,
        status=segment.status,
        geojson=segment.geojson,
    )
