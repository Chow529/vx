from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class PostCreate(BaseModel):
    title: str
    content: str
    tech_stack: str = "其他"
    difficulty: int = 1
    tags: List[str] = []
    also_save_to_my: bool = False  # 是否同步存入个人题库


class PostOut(BaseModel):
    id: int
    title: str
    content: str
    images: str
    tech_stack: str
    difficulty: int
    is_solved: bool
    like_count: int
    comment_count: int
    created_at: datetime
    user_nickname: str = ""
    user_avatar: str = ""
    tags: List[str] = []

    class Config:
        from_attributes = True


class PostListOut(BaseModel):
    total: int
    items: List[PostOut]


class CommentCreate(BaseModel):
    content: str
    parent_id: Optional[int] = None


class CommentOut(BaseModel):
    id: int
    post_id: int
    content: str
    parent_id: Optional[int]
    is_adopted: bool
    like_count: int
    created_at: datetime
    user_nickname: str = ""
    user_avatar: str = ""
    replies: List["CommentOut"] = []

    class Config:
        from_attributes = True
