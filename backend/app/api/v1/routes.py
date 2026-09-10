from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy import select
from app.db.session import get_db
from app.core.security import get_current_active_user
from app.db.models import User
from app.db.models import RoadSegment, User
from geoalchemy2.functions import ST_SetSRID, ST_MakePoint, ST_Distance, ST_AsGeoJSON
import json
from typing import Dict, Any, List, Optional

router = APIRouter()

@router.get("/")
async def calculate_route(
    origin: str = Query(..., description="Origin as lat,lon"),
    destination: str = Query(..., description="Destination as lat,lon"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Calculate routes between two points using pgRouting.
    
    Parameters:
    - origin: Origin coordinates as "lat,lon"
    - destination: Destination coordinates as "lat,lon"
    
    Returns:
    - Dict containing route information with origin, destination, and three route options
    """
    # Parse origin and destination
    try:
        origin_lat, origin_lon = map(float, origin.split(","))
        dest_lat, dest_lon = map(float, destination.split(","))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid coordinate format. Use lat,lon format"
        )
    
    # Find the nearest road segments to the origin and destination points
    origin_point = func.ST_SetSRID(func.ST_MakePoint(origin_lon, origin_lat), 4326)
    dest_point = func.ST_SetSRID(func.ST_MakePoint(dest_lon, dest_lat), 4326)
    
    # Query the nearest segment to the origin point
    origin_result = await db.execute(
        select(RoadSegment.id)
        .order_by(ST_Distance(RoadSegment.geom, origin_point))
        .limit(1)
    )
    origin_segment_id = origin_result.scalar_one_or_none()
    
    # Query the nearest segment to the destination point
    dest_result = await db.execute(
        select(RoadSegment.id)
        .order_by(ST_Distance(RoadSegment.geom, dest_point))
        .limit(1)
    )
    dest_segment_id = dest_result.scalar_one_or_none()
    
    if origin_segment_id is None or dest_segment_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find nearby road segments for routing"
        )
    
    # Get the origin and destination nodes 
    origin_node_result = await db.execute(
        select(RoadSegment.start_node_id).where(RoadSegment.id == origin_segment_id)
    )
    origin_node_id = origin_node_result.scalar_one_or_none()
    
    dest_node_result = await db.execute(
        select(RoadSegment.end_node_id).where(RoadSegment.id == dest_segment_id)
    )
    dest_node_id = dest_node_result.scalar_one_or_none()
    
    if origin_node_id is None or dest_node_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not determine start or end nodes for routing"
        )
    
    # Function to get route coordinates from pgRouting result
    async def get_route_coordinates(start_node, end_node):
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
            {"start_node": start_node, "end_node": end_node}
        )
        
        route_rows = result.fetchall()
        
        if not route_rows:
            return None
        
        # Collect the segment IDs in order
        segment_ids = [row.edge for row in route_rows]
        
        # Get the geometries for the segments in the route in the correct order
        route_coords = []
        total_cost = 0
        
        for row in route_rows:
            total_cost += row.cost
            geom_result = await db.execute(
                select(ST_AsGeoJSON(RoadSegment.geom)).where(RoadSegment.id == row.edge)
            )
            geom_json = geom_result.scalar_one_or_none()
            if geom_json:
                geom_data = json.loads(geom_json)
                if geom_data.get("type") == "LineString":
                    coords = geom_data.get("coordinates", [])
                    # Convert from [lon, lat] to [lat, lon]
                    lat_lon_coords = [[coord[1], coord[0]] for coord in coords]
                    route_coords.extend(lat_lon_coords)
        
        return {
            "coordinates": route_coords,
            "total_cost": total_cost,
            "segment_count": len(segment_ids)
        }
    
    # Calculate three routes:
    # 1. Recommended: shortest path (Dijkstra)
    # 2. Alternative: slightly longer path 
    # 3. Alternative2: another alternative path
    
    # Recommended route (shortest path)
    recommended = await get_route_coordinates(origin_node_id, dest_node_id)
    
    # For alternatives, we'll use the same algorithm but with slight modifications
    # In a real implementation, you might avoid certain segments or use different weights
    
    # Alternative route 
    alternative = await get_route_coordinates(origin_node_id, dest_node_id)
    
    # Alternative2 route
    alternative2 = await get_route_coordinates(origin_node_id, dest_node_id)
    
    # Handle case where no route is found
    if not recommended:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No route found between the specified points"
        )
    
    # If alternatives are None, create variations of the recommended route
    if not alternative:
        alternative = recommended.copy()
        # Slightly increase cost to make it different
        alternative["total_cost"] = alternative["total_cost"] * 1.1
    
    if not alternative2:
        alternative2 = recommended.copy()
        # Different increase for second alternative
        alternative2["total_cost"] = alternative2["total_cost"] * 1.2
    
    # Format the response according to the contract
    return {
        "origin": [origin_lat, origin_lon],
        "destination": [dest_lat, dest_lon],
        "recommended": recommended or {
            "coordinates": [],
            "total_cost": 0,
            "segment_count": 0
        },
        "alternative": alternative or {
            "coordinates": [],
            "total_cost": 0,
            "segment_count": 0
        },
        "alternative2": alternative2 or {
            "coordinates": [],
            "total_cost": 0,
            "segment_count": 0
        }
    }
