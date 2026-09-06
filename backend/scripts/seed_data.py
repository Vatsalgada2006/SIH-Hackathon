#!/usr/bin/env python3
"""
Test script to check syntax.
"""
import asyncio
from app.db.models import Incident, WeatherSnapshot, LandslideEvent, VehicleProfile
from app.db.models.incident import IncidentType, IncidentSeverity, IncidentStatus
from app.db.models.vehicle import VehicleType
from geoalchemy2.elements import WKTElement
from geoalchemy2.shape import from_shape
from shapely.geometry import Point, LineString
import csv
import json
import os
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal

# Vehicle profile reference data (would normally be imported from JSON)
VEHICLE_PROFILES = [
    {
        "vehicle_class": "HEAVY_CARGO_TRUCK",
        "payload_capacity_tons": 40.0,
        "base_plains_speed_kmh": 80.0,
        "base_hills_speed_kmh": 50.0,
        "max_slope_gradient_pct": 7.0,
        "max_wind_speed_kmh": 90.0,
        "rain_slowdown_factor": 0.3,
        "risk_tolerance_threshold": 0.6,
        "eligible_for_restricted_bridges": False
    },
    {
        "vehicle_class": "MEDIUM_COMMERCIAL_VEHICLE",
        "payload_capacity_tons": 15.0,
        "base_plains_speed_kmh": 90.0,
        "base_hills_speed_kmh": 60.0,
        "max_slope_gradient_pct": 12.0,
        "max_wind_speed_kmh": 100.0,
        "rain_slowdown_factor": 0.2,
        "risk_tolerance_threshold": 0.5,
        "eligible_for_restricted_bridges": True
    },
    {
        "vehicle_class": "LIGHT_4X4_SUPPLY_PICKUP",
        "payload_capacity_tons": 5.0,
        "base_plains_speed_kmh": 100.0,
        "base_hills_speed_kmh": 70.0,
        "max_slope_gradient_pct": 25.0,
        "max_wind_speed_kmh": 120.0,
        "rain_slowdown_factor": 0.1,
        "risk_tolerance_threshold": 0.4,
        "eligible_for_restricted_bridges": True
    },
    {
        "vehicle_class": "EMERGENCY_DISASTER_RELIEF_VAN",
        "payload_capacity_tons": 3.0,
        "base_plains_speed_kmh": 110.0,
        "base_hills_speed_kmh": 80.0,
        "max_slope_gradient_pct": 15.0,
        "max_wind_speed_kmh": 130.0,
        "rain_slowdown_factor": 0.05,
        "risk_tolerance_threshold": 0.3,
        "eligible_for_restricted_bridges": True
    }
]

async def seed_incidents(db: AsyncSession):
    """Seed incidents from CSV file."""
    csv_path = "/c/Users/vatsa/OneDrive/Documents/SIH-HACKATHON/data/incidents/ner_road_incidents.csv"
    if not os.path.exists(csv_path):
        print(f"Incidents CSV file not found: {csv_path}")
        return
    
    print(f"Seeding incidents from {csv_path}")
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        incidents_to_add = []
        for row in reader:
            # Check if incident already exists (by description and reported_time as a simple heuristic)
            # In a real system, you might have a unique ID or use more sophisticated deduplication
            stmt = select(Incident).where(
                Incident.description == row["description"],
                Incident.reported_at == datetime.fromisoformat(row["reported_time"].replace("Z", "+00:00"))
            )
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if not existing:
                # Create point from latitude and longitude
                point = WKTElement(f"POINT({row["longitude"]} {row["latitude"]})", srid=4326)
                
                incident = Incident(
                    description=row["description"],
                    incident_type=row["incident_type"],
                    severity=row["severity"],
                    geom=point,
                    passable_for=row["passable_for"],
                    estimated_clearance_time_hrs=int(row["estimated_clearance_time_hrs"]) if row["estimated_clearance_time_hrs"] else None,
                    delay_penalty_minutes=int(row["delay_penalty_minutes"]) if row["delay_penalty_minutes"] else None,
                    reporting_agency=row["reporting_agency"],
                    reported_at=datetime.fromisoformat(row["reported_time"].replace("Z", "+00:00")),
                    status=row["status"]
                )
                incidents_to_add.append(incident)
        
        if incidents_to_add:
            db.add_all(incidents_to_add)
            await db.commit()
            print(f"Added {len(incidents_to_add)} incidents")
            print(f"Would add {len(incidents_to_add)} incidents")
        else:
            print("No new incidents to add")

async def seed_weather_snapshots(db: AsyncSession):
    """Seed weather snapshots from CSV file."""
    csv_path = "/c/Users/vatsa/OneDrive/Documents/SIH-HACKATHON/data/weather/ner_live_weather_snapshot.csv"
    if not os.path.exists(csv_path):
        print(f"Weather snapshots CSV file not found: {csv_path}")
        return
    
    print(f"Seeding weather snapshots from {csv_path}")
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        snapshots_to_add = []
        for row in reader:
            # Create point from latitude and longitude
            point = WKTElement(f"POINT({row["longitude"]} {row["latitude"]})", srid=4326)
            
            snapshot = WeatherSnapshot(
                geom=point,
                rainfall=float(row["current_precip_rate_mm_hr"]),
                temperature=float(row["temperature_celsius"]),
                wind_speed=float(row["wind_speed_kmd"]),
                humidity=float(row["humidity_percent"]),
                recorded_at=datetime.utcnow()  # Use current time for seed data
            )
            snapshots_to_add.append(snapshot)
        
        if snapshots_to_add:
            db.add_all(snapshots_to_add)
            await db.commit()
            print(f"Added {len(snapshots_to_add)} weather snapshots")
        else:
            print("No new weather snapshots to add")
async def seed_landslide_events(db: AsyncSession):
    """Seed landslide events from CSV file."""
    csv_path = "/c/Users/vatsa/OneDrive/Documents/SIH-HACKATHON/data/landslide_inventory/landslides_NE_India.csv"
    if not os.path.exists(csv_path):
        print(f"Landslide events CSV file not found: {csv_path}")
        return
    
    print(f"Seeding landslide events from {csv_path}")
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        events_to_add = []
        for row in reader:
            # Create point from latitude and longitude
            point = WKTElement(f"POINT({row["longitude"]} {row["latitude"]})", srid=4326)
            
            # Parse date if provided
            date_obj = None
            if row["date"]:
                try:
                    date_obj = datetime.fromisoformat(row["date"])
                except ValueError:
                    pass  # Keep as None if parsing fails
            
            event = LandslideEvent(
                landslide_category=row["landslide_category"],
                landslide_trigger=row["landslide_trigger"],
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                fatalities=int(row["fatalities"]) if row["fatalities"] else None,
                injuries=int(row["injuries"]) if row["injuries"] else None,
                date=date_obj,
                location_details=row["location_details"],
                geom=point
            )
            events_to_add.append(event)
        
        if events_to_add:
            db.add_all(events_to_add)
            await db.commit()
            print(f"Added {len(events_to_add)} landslide events")
        else:
            print("No new landslide events to add")
async def seed_vehicle_profiles(db: AsyncSession):
    """Seed vehicle profiles from reference data."""
    print("Seeding vehicle profiles")
    profiles_to_add = []
    for profile_data in VEHICLE_PROFILES:
        # Check if profile already exists
        stmt = select(VehicleProfile).where(VehicleProfile.vehicle_class == profile_data["vehicle_class"])
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if not existing:
            profile = VehicleProfile(**profile_data)
            profiles_to_add.append(profile)
    
    if profiles_to_add:
        db.add_all(profiles_to_add)
    else:
        print("No new vehicle profiles to add")

async def seed_all():
    """Run all seed functions."""
    async with AsyncSessionLocal() as db:
        await seed_incidents(db)
        await seed_weather_snapshots(db)
        await seed_landslide_events(db)
        await seed_vehicle_profiles(db)
        print("Data seeding completed!")

if __name__ == "__main__":
    asyncio.run(seed_all())

