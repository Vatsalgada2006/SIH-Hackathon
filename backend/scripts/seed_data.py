#!/usr/bin/env python3
"""
Seed application database with project data.

All data paths are resolved relative to the backend project root,
so the script works across different machines/environments.
"""

import asyncio
import csv
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from geoalchemy2.elements import WKTElement

from app.db.models import (
    Incident,
    WeatherSnapshot,
    LandslideEvent,
    VehicleProfile,
)
from app.db.session import AsyncSessionLocal


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# backend/
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# backend/data/
DATA_DIR = PROJECT_ROOT / "data"


# ---------------------------------------------------------------------------
# Vehicle reference data
# ---------------------------------------------------------------------------

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
        "eligible_for_restricted_bridges": False,
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
        "eligible_for_restricted_bridges": True,
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
        "eligible_for_restricted_bridges": True,
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
        "eligible_for_restricted_bridges": True,
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_datetime(value: str | None):
    """Parse an ISO datetime safely."""
    if not value:
        return None

    value = value.strip()

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def map_incident_status(status: str | None) -> str | None:
    """Map CSV incident status values to database-allowed values."""
    if not status:
        return None

    status = status.strip().upper()

    # Map CSV status values to database enum values
    status_mapping = {
        'ACTIVE': 'VERIFIED',
        'CLEARING_IN_PROGRESS': 'VERIFIED',
        # Add any other mappings as needed
    }

    return status_mapping.get(status, 'PENDING')  # Default to PENDING for unknown values


def map_incident_type(incident_type: str | None) -> str | None:
    """Map CSV incident type values to database-allowed values."""
    if not incident_type:
        return None

    incident_type = incident_type.strip().upper()

    # Map CSV incident type values to database enum values
    type_mapping = {
        'LANDSLIDE_BLOCKAGE': 'LANDSLIDE',
        'ROAD_COLLAPSE_EROSION': 'OTHER',
        'WATERLOGGING_FLOOD': 'FLOOD',
        'BRIDGE_MAINTENANCE': 'CONSTRUCTION',
        'MUDSLIDE_SLOWDOWN': 'LANDSLIDE',
        'BORDER_CHECKPOST_CONGESTION': 'OTHER',
        # Add any other mappings as needed
    }

    return type_mapping.get(incident_type, 'OTHER')  # Default to OTHER for unknown values


def map_incident_severity(severity: str | None) -> str | None:
    """Map CSV incident severity values to database-allowed values."""
    if not severity:
        return None

    severity = severity.strip().upper()

    # Map CSV severity values to database enum values
    severity_mapping = {
        'MODERATE': 'MEDIUM',
        # Add any other mappings as needed
    }

    return severity_mapping.get(severity, severity)  # Return original if no mapping needed


def map_landslide_category(category: str | None) -> str | None:
    """Map CSV landslide category values to database-allowed values (max 50 chars)."""
    if not category:
        return None

    category = category.strip()

    # If already within limit, return as-is
    if len(category) <= 50:
        return category

    # Map long descriptive categories to standardized ones
    category_mapping = {
        'Rock slide / rock fall in interbedded sandstone–shale': 'ROCK_FALL',
        'Translational slide on dipping shale beds': 'SLIDE',
        'Retaining wall failure / debris slide': 'RETAINING_WALL_FAILURE',
        'Quarry collapse / debris slide': 'QUARRY_COLLAPSE',
        'Multiple debris slides': 'DEBRIS_SLIDES',
        'Landslide / road blockage': 'LANDSLIDE_BLOCKAGE',
        'Rainfall-triggered debris slide': 'DEBRIS_FLOW',
        'Debris flow on shale bed (dip 32°)': 'DEBRIS_FLOW',
        'Debris flow': 'DEBRIS_FLOW',
        'Multiple types (retaining wall, rockfall)': 'MIXED_TYPES',
        # Add any other mappings as needed
    }

    return category_mapping.get(category, 'OTHER')  # Default to OTHER for unknown values


def make_point(longitude: str, latitude: str) -> WKTElement:
    """Create an EPSG:4326 point."""
    return WKTElement(
        f"POINT({longitude} {latitude})",
        srid=4326,
    )


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------

async def seed_incidents(db: AsyncSession):
    csv_path = DATA_DIR / "incidents" / "ner_road_incidents.csv"

    if not csv_path.exists():
        print(f"[SKIP] Incidents CSV not found: {csv_path}")
        return

    print(f"[INFO] Reading incidents from: {csv_path}")

    added = 0

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            reported_at = parse_datetime(row.get("reported_time"))

            if reported_at is None:
                print("[WARN] Skipping incident with invalid reported_time")
                continue

            stmt = select(Incident).where(
                Incident.description == row.get("description"),
                Incident.reported_at == reported_at,
            )

            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                continue

            latitude = row.get("latitude")
            longitude = row.get("longitude")

            if not latitude or not longitude:
                print("[WARN] Skipping incident without coordinates")
                continue

            incident = Incident(
                description=row.get("description"),
                incident_type=map_incident_type(row.get("incident_type")),
                severity=map_incident_severity(row.get("severity")),
                geom=make_point(longitude, latitude),
                passable_for=row.get("passable_for"),
                estimated_clearance_time_hrs=(
                    int(float(row["estimated_clearance_time_hrs"]))
                    if row.get("estimated_clearance_time_hrs")
                    else None
                ),
                delay_penalty_minutes=(
                    int(row["delay_penalty_minutes"])
                    if row.get("delay_penalty_minutes")
                    else None
                ),
                reporting_agency=row.get("reporting_agency"),
                reported_at=reported_at,
                status=map_incident_status(row.get("status")),
            )

            db.add(incident)
            added += 1

    await db.commit()

    print(f"[OK] Added {added} incidents")


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------

async def seed_weather_snapshots(db: AsyncSession):
    csv_path = DATA_DIR / "weather" / "ner_live_weather_snapshot.csv"

    if not csv_path.exists():
        print(f"[SKIP] Weather CSV not found: {csv_path}")
        return

    print(f"[INFO] Reading weather from: {csv_path}")

    added = 0

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            latitude = row.get("latitude")
            longitude = row.get("longitude")

            if not latitude or not longitude:
                print("[WARN] Skipping weather record without coordinates")
                continue

            snapshot = WeatherSnapshot(
                geom=make_point(longitude, latitude),
                rainfall=float(row.get("current_precip_rate_mm_hr") or 0),
                temperature=float(row.get("temperature_celsius") or 0),
                wind_speed=float(row.get("wind_speed_kmd") or 0),
                humidity=float(row.get("humidity_percent") or 0),
                recorded_at=datetime.utcnow(),
            )

            db.add(snapshot)
            added += 1

    await db.commit()

    print(f"[OK] Added {added} weather snapshots")


# ---------------------------------------------------------------------------
# Landslides
# ---------------------------------------------------------------------------

async def seed_landslide_events(db: AsyncSession):
    csv_path = (
        DATA_DIR
        / "landslide_inventory"
        / "landslides_NE_India.csv"
    )

    if not csv_path.exists():
        print(f"[SKIP] Landslide CSV not found: {csv_path}")
        return

    print(f"[INFO] Reading landslides from: {csv_path}")

    added = 0

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            latitude = row.get("latitude")
            longitude = row.get("longitude")

            if not latitude or not longitude:
                print("[WARN] Skipping landslide without coordinates")
                continue

            event = LandslideEvent(
                landslide_category=map_landslide_category(row.get("landslide_category")),
                landslide_trigger=row.get("landslide_trigger"),
                latitude=float(latitude),
                longitude=float(longitude),
                fatalities=(
                    int(row["fatalities"])
                    if row.get("fatalities")
                    else None
                ),
                injuries=(
                    int(row["injuries"])
                    if row.get("injuries")
                    else None
                ),
                date=parse_datetime(row.get("date")),
                location_details=row.get("location_details"),
                geom=make_point(longitude, latitude),
            )

            db.add(event)
            added += 1

    await db.commit()

    print(f"[OK] Added {added} landslide events")


# ---------------------------------------------------------------------------
# Vehicle profiles
# ---------------------------------------------------------------------------

async def seed_vehicle_profiles(db: AsyncSession):
    print("[INFO] Seeding vehicle profiles")

    added = 0

    for profile_data in VEHICLE_PROFILES:
        stmt = select(VehicleProfile).where(
            VehicleProfile.vehicle_class
            == profile_data["vehicle_class"]
        )

        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            continue

        profile = VehicleProfile(**profile_data)

        db.add(profile)
        added += 1

    await db.commit()

    print(f"[OK] Added {added} vehicle profiles")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def seed_all():
    print("=" * 60)
    print("SIH NER SMART LOGISTICS - DATABASE SEED")
    print("=" * 60)

    print(f"Project root: {PROJECT_ROOT}")
    print(f"Data directory: {DATA_DIR}")
    print()

    if not DATA_DIR.exists():
        raise FileNotFoundError(
            f"Data directory does not exist: {DATA_DIR}"
        )

    async with AsyncSessionLocal() as db:
        await seed_incidents(db)
        await seed_weather_snapshots(db)
        await seed_landslide_events(db)
        await seed_vehicle_profiles(db)

    print()
    print("=" * 60)
    print("DATA SEEDING COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed_all())