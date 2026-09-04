from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from app.db.base import Base, created_at, updated_at

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)  # ADMIN, CONTROL_ROOM, FIELD_OFFICER, DRIVER
    is_active = Column(Boolean, nullable=False, server_default="true")
    # Inherited columns: created_at, updated_at

    # Relationships
    reported_incidents = relationship("Incident", foreign_keys="Incident.reporter_id")
    verified_incidents = relationship("Incident", foreign_keys="Incident.verified_by")

    # Check constraint for role
    __table_args__ = (
        CheckConstraint(role.in_(['ADMIN', 'CONTROL_ROOM', 'FIELD_OFFICER', 'DRIVER']), name='valid_user_role'),
    )

    def __repr__(self):
        return f"<User id={self.id} username='{self.username}' role={self.role}>"