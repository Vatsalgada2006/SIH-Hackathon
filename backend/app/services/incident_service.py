from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from geoalchemy2.functions import ST_Distance, ST_SetSRID, ST_MakePoint
from app.db.models import Incident, User, AuditLog, RoadSegment
from app.db.models.incident import IncidentStatus, IncidentType, IncidentSeverity
from app.services.accessibility_service import AccessibilityService
from typing import List, Optional
from datetime import datetime

# Helper function to create an audit log entry
async def create_audit_log(
    db: AsyncSession,
    user_id: Optional[int],
    action: str,
    table_name: str,
    record_id: int,
    changes: str = None,
    ip_address: str = None
):
    audit_log = AuditLog(
        user_id=user_id,
        action=action,
        table_name=table_name,
        record_id=record_id,
        changes=changes,
        ip_address=ip_address
    )
    db.add(audit_log)
    await db.commit()
    await db.refresh(audit_log)
    return audit_log

class IncidentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_incident(self, incident_id: int) -> Optional[Incident]:
        print(f"get_incident called with incident_id={incident_id}")
        result = await self.db.execute(select(Incident).where(Incident.id == incident_id))
        return result.scalar_one_or_none()

    async def get_incidents(
        self,
        skip: int = 0,
        limit: int = 100,
        incident_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Incident]:
        query = select(Incident)
        if incident_type:
            query = query.where(Incident.incident_type == incident_type)
        if status:
            query = query.where(Incident.status == status)
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def create_incident(
        self,
        reporter_id: Optional[int],
        description: str,
        incident_type: str,
        severity: str,
        latitude: float,
        longitude: float,
        segment_id: Optional[int] = None,
    ) -> Incident:
        # Create point from latitude and longitude
        point = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
        
        # If segment_id is not provided, find the nearest road segment
        if segment_id is None:
            # Query the nearest segment
            query = (
                select(RoadSegment.id)
                .order_by(ST_Distance(RoadSegment.geom, point))
                .limit(1)
            )
            result = await self.db.execute(query)
            segment_id = result.scalar_one_or_none()
            if segment_id is None:
                raise ValueError("No road segments found")
        # Create the incident
        incident = Incident(
            reporter_id=reporter_id,
            description=description,
            incident_type=incident_type,
            severity=severity,
            geom=point,
            segment_id=segment_id,
            reported_at=datetime.utcnow(),
            status=IncidentStatus.PENDING.value,
        )
        self.db.add(incident)
        await self.db.commit()
        await self.db.refresh(incident)
        print(f"Incident after refresh: {incident}")

        # Create audit log for incident creation
        await create_audit_log(
            db=self.db,
            user_id=reporter_id,
            action="CREATE_INCIDENT",
            table_name="incidents",
            record_id=incident.id,
            changes=f"Created incident of type {incident_type} with severity {severity}",
        )

        return incident

    async def update_incident(
        self,
        incident_id: int,
        reporter_id: Optional[int] = None,
        description: Optional[str] = None,
        incident_type: Optional[str] = None,
        severity: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        segment_id: Optional[int] = None,
    ) -> Optional[Incident]:
        incident = await self.get_incident(incident_id)
        if not incident:
            return None

        update_data = {}
        if reporter_id is not None:
            update_data["reporter_id"] = reporter_id
        if description is not None:
            update_data["description"] = description
        if incident_type is not None:
            update_data["incident_type"] = incident_type
        if severity is not None:
            update_data["severity"] = severity
        if latitude is not None:
            update_data["latitude"] = latitude
        if longitude is not None:
            update_data["longitude"] = longitude
        if segment_id is not None:
            update_data["segment_id"] = segment_id

        if update_data:
            await self.db.execute(
                update(Incident)
                .where(Incident.id == incident_id)
                .values(**update_data)
            )
            await self.db.commit()
            await self.db.refresh(incident)

            # Create audit log for incident update
            await create_audit_log(
                db=self.db,
                user_id=reporter_id,
                action="UPDATE_INCIDENT",
                table_name="incidents",
                record_id=incident.id,
                changes=f"Updated incident: {update_data}",
            )

        return incident

    async def verify_incident(
        self,
        incident_id: int,
        verified_by: int,
    ) -> Optional[Incident]:
        print(f"verify_incident called with incident_id={incident_id}, verified_by={verified_by}")
        incident = await self.get_incident(incident_id)
        print(f"incident from get_incident: {incident}")
        if not incident:
            return None

        incident.verified_at = datetime.utcnow()
        incident.verified_by = verified_by
        incident.status = IncidentStatus.VERIFIED.value

        await self.db.commit()
        await self.db.refresh(incident)

        # Create audit log for incident verification
        await create_audit_log(
            db=self.db,
            user_id=verified_by,
            action="VERIFY_INCIDENT",
            table_name="incidents",
            record_id=incident.id,
            changes=f"Incident verified by user {verified_by}",
        )

        # Update the accessibility of the associated road segment
        if incident.segment_id is not None:
            accessibility_service = AccessibilityService(self.db)
            try:
                await accessibility_service.update_segment_accessibility(incident.segment_id, force=True)
            except Exception:
                # Ignore errors in accessibility update to not fail verification
                pass

        return incident
    async def resolve_incident(
        self,
        incident_id: int,
    ) -> Optional[Incident]:
        incident = await self.get_incident(incident_id)
        if not incident:
            return None

        incident.resolved_at = datetime.utcnow()
        incident.status = IncidentStatus.RESOLVED.value

        await self.db.commit()
        await self.db.refresh(incident)

        # Create audit log for incident resolution
        await create_audit_log(
            db=self.db,
            user_id=None,  # System action
            action="RESOLVE_INCIDENT",
            table_name="incidents",
            record_id=incident.id,
            changes=f"Incident resolved",
        )

        # Update the accessibility of the associated road segment
        if incident.segment_id is not None:
            accessibility_service = AccessibilityService(self.db)
            try:
                await accessibility_service.update_segment_accessibility(incident.segment_id, force=True)
            except Exception:
                # Ignore errors in accessibility update to not fail resolution
                pass

        return incident
    async def delete_incident(
        self,
        incident_id: int,
    ) -> bool:
        incident = await self.get_incident(incident_id)
        if not incident:
            return False

        await self.db.execute(delete(Incident).where(Incident.id == incident_id))
        await self.db.commit()

        # Create audit log for incident deletion
        await create_audit_log(
            db=self.db,
            user_id=None,  # System action
            action="DELETE_INCIDENT",
            table_name="incidents",
            record_id=incident_id,
            changes=f"Incident deleted",
        )

        return True