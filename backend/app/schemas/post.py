from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class PostCreate(BaseModel):
    title: str
    content: str
    answer: str = ""  # 参考答案，可不填
    tech_stack: str = "其他"
    difficulty: int = 1
    tags: List[str] = []
    also_save_to_my: bool = False  # 是否同时存入个人题库（不存则可在社区收藏）


class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    answer: Optional[str] = None
    tech_stack: Optional[str] = None
    difficulty: Optional[int] = None


class PostOut(BaseModel):
    id: int
    user_id: int = 0
    title: str
    content: str
    answer: str = ""        # 参考答案
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
    is_liked: bool = False      # 当前用户是否已点赞
    is_collected: bool = False  # 当前用户是否已收藏到题库
    is_own: bool = False        # 是否为当前用户本人发布
    can_manage: bool = False    # 当前用户是否可管理（本人或管理员）：编辑帖子 / 删除评论

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
    user_id: int = 0
    content: str
    parent_id: Optional[int]
    is_adopted: bool
    like_count: int
    created_at: datetime
    user_nickname: str = ""
    user_avatar: str = ""
    is_liked: bool = False  # 当前用户是否已点赞该评论
    can_delete: bool = False  # 当前用户是否可删除该评论（评论者/楼主/管理员）
    replies: List["CommentOut"] = []

    class Config:
        from_attributes = True
