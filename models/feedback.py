import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, SmallInteger, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_id = Column(UUID(as_uuid=True), ForeignKey("query_logs.query_id"), nullable=False, index=True)
    rating = Column(SmallInteger, nullable=False)  # +1 or -1
    comment = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
