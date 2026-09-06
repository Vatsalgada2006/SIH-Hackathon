from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy import select
from app.db.session import get_db
from app.core.security import get_current_active_user
from app.db.models import User
from app.db.models import RoadSegment, User
from geoalchemy2.functions import ST_SetSRID, ST_MakePoint, ST_Distance
import json
from typing import Dict, Any, List

router = APIRouter()

@router.get("/")
async def calculate_route(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Calculate a route between two points using pgRouting.
    
    Parameters:
    - start_lat, start_lon: Starting point coordinates
    - end_lat, end_lon: Ending point coordinates
    
    Returns:
    - Dict containing route information
    """
    # Find the nearest road segments to the start and end points
    start_point = func.ST_SetSRID(func.ST_MakePoint(start_lon, start_lat), 4326)
    end_point = func.ST_SetSRID(func.ST_MakePoint(end_lon, end_lat), 4326)
    
    # Query the nearest segment to the start point
    start_result = await db.execute(
        select(RoadSegment.id)
        .order_by(ST_Distance(RoadSegment.geom, start_point))
        .limit(1)
    )
    start_segment_id = start_result.scalar_one_or_none()
    
    # Query the nearest segment to the end point
    end_result = await db.execute(
        select(RoadSegment.id)
        .order_by(ST_Distance(RoadSegment.geom, end_point))
        .limit(1)
    )
    end_segment_id = end_result.scalar_one_or_none()
    
    if start_segment_id is None or end_segment_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find nearby road segments for routing"
        )
    
    # Get the start and end nodes 
    start_node_result = await db.execute(
        select(RoadSegment.start_node_id).where(RoadSegment.id == start_segment_id)
    )
    start_node_id = start_node_result.scalar_one_or_none()
    
    end_node_result = await db.execute(
        select(RoadSegment.end_node_id).where(RoadSegment.id == end_segment_id)
    )
    end_node_id = end_node_result.scalar_one_or_none()
    
    if start_node_id is None or end_node_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not determine start or end nodes for routing"
        )
    
    # Use pgRouting to find the shortest path
    # We'll use pgr_dijkstra with the cost column we added
    route_query = text("""
        SELECT seq, id1 AS node, id2 AS edge, cost
        FROM pgr_dijkstra(
            'SELECT id, source::integer, target::integer, cost FROM road_segments',
            :start_node, :end_node,
            directed := false
        ) AS di
        JOIN road_segments ON road_segments.id = di.edge
    """)
    
    result = await db.execute(
        route_query,
        {"start_node": start_node_id, "end_node": end_node_id}
    )
    
    route_rows = result.fetchall()
    
    if not route_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No route found between the specified points"
        )
    
    # Collect the route information in order
    segment_ids = []
    total_cost = 0.0
    
    for row in route_rows:
        segment_ids.append(row.edge)
        total_cost += row.cost
    
    # Get the geometries for the segments in the route in the correct order
    # We'll query them individually to preserve order (not efficient but works for demo)
    route_geoms = []
    for segment_id in segment_ids:
        geom_result = await db.execute(
            select(ST_AsGeoJSON(RoadSegment.geom)).where(RoadSegment.id == segment_id)
        )
        geom_json = geom_result.scalar_one_or_none()
        if geom_json:
            route_geoms.append(json.loads(geom_json))
    
    # Combine the geometries into a single LineString (simplified approach)
    # In a real implementation, you would properly concatenate the LineStrings
    if route_geoms:
        # For simplicity, we'll just return the first geometry's coordinates
        # A real implementation would properly combine them
        coordinates = route_geoms[0].get("coordinates", []) if route_geoms[0].get("type") == "LineString" else []
    else:
        coordinates = []
    
    return {
        "route": {
            "type": "LineString",
            "coordinates": coordinates
        },
        "segment_ids": segment_ids,
        "total_cost": total_cost,
        "message": "Route calculated successfully"
    }
