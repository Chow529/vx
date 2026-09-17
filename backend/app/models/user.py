from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text

from ..database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(String(128), unique=True, nullable=False, index=True)
    nickname = Column(String(64), default="")
    avatar_url = Column(String(512), default="")
    reputation = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
