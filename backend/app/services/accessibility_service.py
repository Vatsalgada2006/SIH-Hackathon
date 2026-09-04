from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.db.models import Incident, RoadSegment, AuditLog
from app.db.models.incident import IncidentStatus
from typing import Optional
from datetime import datetime

class AccessibilityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _is_blocking_incident(incident_type: str, severity: str) -> bool:
        """
        Determine if an incident should cause BLOCKED status.
        """
        blocking_types = {
            'LANDSLIDE': ['HIGH', 'CRITICAL'],
            'FLOOD': ['HIGH', 'CRITICAL'],
            # Note: ACCIDENT and CONSTRUCTION are not considered blocking by default
            # but can be adjusted based on requirements.
        }
        if incident_type in blocking_types:
            return severity in blocking_types[incident_type]
        return False

    @staticmethod
    def _is_degrading_incident(incident_type: str, severity: str) -> bool:
        """
        Determine if an incident should cause DEGRADED status (if not already BLOCKED).
        """
        # All verified active incidents that are not blocking cause at least DEGRADED
        # But we can define specific rules if needed.
        # For simplicity, we consider all verified active incidents as at least degrading
        # unless they are blocking.
        # However, we want to avoid marking an incident as degrading if it's blocking.
        # So we'll check: if it's not blocking, then it's degrading.
        # But note: we might have incidents that are neither? According to our rules,
        # every verified active incident should affect accessibility.
        # We'll return True for any verified active incident that is not blocking.
        # But we must also consider that some incidents might not affect the road at all?
        # The incident is associated with a segment via nearest point, so we assume it does.
        return not AccessibilityService._is_blocking_incident(incident_type, severity)

    async def _get_active_verifed_incidents_for_segment(self, segment_id: int):
        """
        Retrieve all verified but not resolved incidents for a given segment.
        """
        result = await self.db.execute(
            select(Incident)
            .where(
                Incident.segment_id == segment_id,
                Incident.status == IncidentStatus.VERIFIED.value,
                # resolved_at is NULL means not resolved
                Incident.resolved_at.is_(None)
            )
        )
        return result.scalars().all()

    async def calculate_segment_accessibility(self, segment_id: int) -> str:
        """
        Calculate the accessibility status for a segment based on active verified incidents.
        Returns the new status string based solely on incidents (ignores manual override).
        """
        incidents = await self._get_active_verifed_incidents_for_segment(segment_id)

        if not incidents:
            return "OPEN"

        has_blocking = False
        has_degrading = False

        for incident in incidents:
            if self._is_blocking_incident(incident.incident_type, incident.severity):
                has_blocking = True
                # No need to check further for blocking, but we continue to see if there are multiple
            elif self._is_degrading_incident(incident.incident_type, incident.severity):
                has_degrading = True

        if has_blocking:
            return "BLOCKED"
        elif has_degrading:
            return "DEGRADED"
        else:
            # This should not happen if our rules are correct, but fallback to OPEN
            return "OPEN"



    async def update_segment_accessibility(self, segment_id: int, force: bool = False) -> str:
        """
        Update the accessibility status of a segment in the database.
        Returns the new status.
        If force is False, respects manual overrides and won't overwrite them.
        If force is True, will overwrite manual overrides.
        """
        # If not forcing and there's an active manual override, don't update
        if not force:
            result = await self.db.execute(
                select(RoadSegment).where(RoadSegment.id == segment_id)
            )
            segment = result.scalar_one_or_none()

            if segment is not None and segment.manual_override:
                # Return the current status without updating
                return segment.status

        new_status = await self.calculate_segment_accessibility(segment_id)

        # Update the segment
        await self.db.execute(
            update(RoadSegment)
            .where(RoadSegment.id == segment_id)
            .values(status=new_status)
        )
        await self.db.commit()

        # Optionally, we can create an audit log for automatic changes.
        # But the instructions say audit logging for manual changes.
        # For automatic changes, we can rely on the incident verification/resolution audit logs.
        # However, we can also log the automatic change if desired.
        # We'll skip audit log for automatic changes to avoid too much noise.
        # But we can add it if needed.

        return new_status

    async def manually_update_segment_status(
        self,
        segment_id: int,
        new_status: str,
        user_id: Optional[int] = None,
        reason: Optional[str] = None
    ) -> str:
        """
        Manually update the segment status with audit logging.
        Only for ADMIN and CONTROL_ROOM.
        Sets manual override fields to indicate this status was manually set.
        """
        # Validate the status
        allowed_statuses = ['OPEN', 'DEGRADED', 'BLOCKED', 'UNKNOWN']
        if new_status not in allowed_statuses:
            raise ValueError(f"Invalid status: {new_status}. Must be one of {allowed_statuses}")

        # Get the current status
        result = await self.db.execute(
            select(RoadSegment.status).where(RoadSegment.id == segment_id)
        )
        current_status = result.scalar_one_or_none()

        if current_status is None:
            raise ValueError(f"Segment with id {segment_id} not found")

        # Update the segment with manual override fields
        await self.db.execute(
            update(RoadSegment)
            .where(RoadSegment.id == segment_id)
            .values(
                status=new_status,
                manual_override=True,
                manual_override_reason=reason,
                override_timestamp=datetime.utcnow(),
                override_user_id=user_id
            )
        )
        await self.db.commit()

        # Create audit log
        audit_log = AuditLog(
            user_id=user_id,
            action="MANUALLY_UPDATE_ROAD_STATUS",
            table_name="road_segments",
            record_id=segment_id,
            changes=f"Changed status from {current_status} to {new_status}. Reason: {reason or 'N/A'}",
            ip_address=None  # We don't have IP address in this context
        )
        self.db.add(audit_log)
        await self.db.commit()
        await self.db.refresh(audit_log)

        return new_status
