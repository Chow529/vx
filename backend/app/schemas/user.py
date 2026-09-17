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


class UserInfo(BaseModel):
    id: int
    nickname: str
    avatar_url: str
    reputation: int
    created_at: datetime

    class Config:
        from_attributes = True
