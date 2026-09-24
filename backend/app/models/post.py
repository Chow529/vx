from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, DateTime, Text, Boolean,
    ForeignKey, Table,
)
from sqlalchemy.orm import relationship

from ..database import Base


# 帖子-标签 多对多关联表
post_tags = Table(
    "post_tags",
    Base.metadata,
    Column("post_id", Integer, ForeignKey("posts.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
)


# 帖子点赞关联表（用于「点赞只能一次，再点取消」）
post_likes = Table(
    "post_likes",
    Base.metadata,
    Column("post_id", Integer, ForeignKey("posts.id"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("created_at", DateTime, default=datetime.now),
)


# 评论点赞关联表（同一人对同一评论只能点赞一次，再点取消）
comment_likes = Table(
    "comment_likes",
    Base.metadata,
    Column("comment_id", Integer, ForeignKey("comments.id"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("created_at", DateTime, default=datetime.now),
)


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(256), nullable=False)
    content = Column(Text, nullable=False)
    answer = Column(Text, default="")  # 参考答案（可不填）
    images = Column(String(1024), default="")  # JSON 数组字符串
    tech_stack = Column(String(64), default="其他")
    difficulty = Column(Integer, default=1)
    is_solved = Column(Boolean, default=False)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User", backref="posts")
    tags = relationship("Tag", secondary=post_tags, backref="posts")
    comments = relationship("Comment", backref="post", order_by="Comment.created_at")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    parent_id = Column(Integer, ForeignKey("comments.id"), nullable=True)
    is_adopted = Column(Boolean, default=False)
    like_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User", backref="comments")
    replies = relationship("Comment", backref="parent", remote_side=[id])
