from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, DateTime, Text, Boolean,
    ForeignKey, Table,
)
from sqlalchemy.orm import relationship

from ..database import Base


# 题目-标签 多对多关联表
question_tags = Table(
    "question_tags",
    Base.metadata,
    Column("question_id", Integer, ForeignKey("questions.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(32), unique=True, nullable=False)
    category = Column(String(32), default="tech")


class Question(Base):
    """个人题库"""
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(256), nullable=False)
    content = Column(Text, nullable=False)
    answer = Column(Text, default="")
    tech_stack = Column(String(64), default="其他")
    difficulty = Column(Integer, default=1)
    mastery = Column(Integer, default=0)
    source = Column(String(32), default="manual")
    source_post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    published_post_id = Column(Integer, nullable=True)  # 已发布到社区的帖子 ID
    is_archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    tags = relationship("Tag", secondary=question_tags, backref="questions")


class PublicQuestion(Base):
    """公共题库 - 所有用户可查看，仅上传者可编辑/删除"""
    __tablename__ = "public_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(256), nullable=False)
    content = Column(Text, nullable=False)
    answer = Column(Text, default="")
    tech_stack = Column(String(64), default="其他")
    difficulty = Column(Integer, default=1)
    view_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    user = relationship("User", backref="public_questions")
    comments = relationship("PublicComment", backref="question", order_by="PublicComment.created_at")
