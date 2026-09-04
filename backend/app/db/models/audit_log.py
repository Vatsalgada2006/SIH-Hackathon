from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.db.base import Base
from sqlalchemy.sql import func

class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)  # e.g., CREATE_INCIDENT, VERIFY_INCIDENT
    table_name = Column(String(50), nullable=False)  # e.g., incidents, road_segments
    record_id = Column(Integer, nullable=False)  # Primary key of the record
    changes = Column(String, nullable=True)  # Simple string for changes; could be JSON but we keep it simple for MVP
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6

    # Relationships
    user = relationship("User")

    def __repr__(self):
        return f"<AuditLog id={self.id} action={self.action} table={self.table_name}>"