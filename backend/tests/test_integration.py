import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.incident_service import IncidentService
from app.services.accessibility_service import AccessibilityService
from app.db.models import User, Incident, RoadSegment
from app.db.models.incident import IncidentStatus

@pytest.mark.asyncio
async def test_integration_workflow_field_officer_create_then_control_room_verify_resolve(db_session: AsyncSession):
    # Create a FIELD_OFFICER user
    field_officer = User(
        id=1,
        username="fieldofficer",
        email="field@example.com",
        password_hash="hashed",
        role="FIELD_OFFICER",
        is_active=True
    )
    # Create a CONTROL_ROOM user
    control_room = User(
        id=2,
        username="controlroom",
        email="control@example.com",
        password_hash="hashed",
        role="CONTROL_ROOM",
        is_active=True
    )
    db_session.add_all([field_officer, control_room])
    await db_session.commit()

    # Create a road segment
    segment = RoadSegment(
        id=1,
        start_node_id=1,
        end_node_id=2,
        status="UNKNOWN"
    )
    db_session.add(segment)
    await db_session.commit()

    # Step 1: FIELD_OFFICER creates a LANDSLIDE incident
    incident_service = IncidentService(db_session)
    incident = await incident_service.create_incident(
        reporter_id=field_officer.id,
        description="Landslide on the road",
        incident_type="LANDSLIDE",
        severity="HIGH",
        latitude=0.0,
        longitude=0.0,
        segment_id=None  # Let the service find the nearest segment
    )
    assert incident is not None
    assert incident.status == IncidentStatus.PENDING.value
    # The service should have set the segment_id to the nearest segment (which is our segment)
    assert incident.segment_id == 1

    # After creation, the incident is PENDING, so it should not affect accessibility yet
    accessibility_service = AccessibilityService(db_session)
    status_after_create = await accessibility_service.calculate_segment_accessibility(1)
    assert status_after_create == "OPEN"  # PENDING incident does not affect accessibility

    # Step 2: CONTROL_ROOM verifies the incident
    verified_incident = await incident_service.verify_incident(incident.id, control_room.id)
    assert verified_incident is not None
    assert verified_incident.status == IncidentStatus.VERIFIED.value
    assert verified_incident.verified_by == control_room.id

    # After verification, the incident is VERIFIED and active, so it should affect accessibility
    status_after_verify = await accessibility_service.calculate_segment_accessibility(1)
    # Since the incident is LANDSLIDE with HIGH severity, it should be BLOCKED
    assert status_after_verify == "BLOCKED"

    # Step 3: CONTROL_ROOM resolves the incident
    resolved_incident = await incident_service.resolve_incident(incident.id)
    assert resolved_incident is not None
    assert resolved_incident.status == IncidentStatus.RESOLVED.value
    assert resolved_incident.resolved_at is not None

    # After resolution, there are no active verified incidents, so the segment should be OPEN
    status_after_resolve = await accessibility_service.calculate_segment_accessibility(1)
    assert status_after_resolve == "OPEN"

@pytest.mark.asyncio
async def test_integration_workflow_multiple_incidents_precedence(db_session: AsyncSession):
    # Create a CONTROL_ROOM user
    control_room = User(
        id=1,
        username="controlroom",
        email="control@example.com",
        password_hash="hashed",
        role="CONTROL_ROOM",
        is_active=True
    )
    db_session.add(control_room)
    await db_session.commit()

    # Create a road segment
    segment = RoadSegment(
        id=1,
        start_node_id=1,
        end_node_id=2,
        status="UNKNOWN"
    )
    db_session.add(segment)
    await db_session.commit()

    # Create two incidents: one degrading and one blocking
    incident_service = IncidentService(db_session)
    accessibility_service = AccessibilityService(db_session)

    # Create a degrading incident (LANDSLIDE MEDIUM)
    incident1 = await incident_service.create_incident(
        reporter_id=control_room.id,
        description="Medium landslide",
        incident_type="LANDSLIDE",
        severity="MEDIUM",
        latitude=0.0,
        longitude=0.0,
        segment_id=None
    )
    assert incident1.segment_id == 1

    # Create a blocking incident (FLOOD HIGH)
    incident2 = await incident_service.create_incident(
        reporter_id=control_room.id,
        description="Severe flood",
        incident_type="FLOOD",
        severity="HIGH",
        latitude=0.0,
        longitude=0.0,
        segment_id=None
    )
    assert incident2.segment_id == 1

    # Both incidents are PENDING, so no effect on accessibility
    status_after_pending = await accessibility_service.calculate_segment_accessibility(1)
    assert status_after_pending == "OPEN"

    # Verify the degrading incident
    await incident_service.verify_incident(incident1.id, control_room.id)
    status_after_verifying_degrading = await accessibility_service.calculate_segment_accessibility(1)
    assert status_after_verifying_degrading == "DEGRADED"  # Only one incident, degrading

    # Verify the blocking incident
    await incident_service.verify_incident(incident2.id, control_room.id)
    status_after_verifying_both = await accessibility_service.calculate_segment_accessibility(1)
    assert status_after_verifying_both == "BLOCKED"  # Blocking takes precedence

    # Resolve the blocking incident
    await incident_service.resolve_incident(incident2.id)
    status_after_resolving_blocking = await accessibility_service.calculate_segment_accessibility(1)
    assert status_after_resolving_blocking == "DEGRADED"  # Only the degrading incident remains

    # Resolve the degrading incident
    await incident_service.resolve_incident(incident1.id)
    status_after_resolving_all = await accessibility_service.calculate_segment_accessibility(1)
    assert status_after_resolving_all == "OPEN"  # No active incidents

