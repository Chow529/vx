from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class WxLoginRequest(BaseModel):
    code: str
    nickname: str = ""
    avatar_url: str = ""


class TokenResponse(BaseModel):
    token: str
    user_id: int
    nickname: str
    avatar_url: str
    is_admin: bool = False  # 前端据此决定是否显示管理入口


class UserInfo(BaseModel):
    id: int
    nickname: str
    avatar_url: str
    reputation: int
    is_admin: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class ProfileUpdate(BaseModel):
    """完善个人资料（头像昵称填写能力收集后提交）"""
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
