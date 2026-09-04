from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, DateTime, func
from sqlalchemy.sql import text

class Base(DeclarativeBase):
    pass

# Common columns
created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)