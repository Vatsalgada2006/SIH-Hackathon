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

    # Step 2: CONTROL_ROOM veries the incident
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

