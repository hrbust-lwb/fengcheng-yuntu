from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Text, DateTime
from app.database import Base

class TripRecord(Base):
    """行程持久化记录表"""
    __tablename__ = "trip_records"

    trip_id = Column(String(64), primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    destination = Column(String(64), default="泰州")
    days = Column(Integer, nullable=False)
    budget = Column(Float, nullable=False)
    start_date = Column(String(32), nullable=False)
    summary = Column(Text, nullable=True)

    # 完整行程 JSON 字符串
    plan_json = Column(Text, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)