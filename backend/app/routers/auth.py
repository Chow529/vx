"""用户认证路由"""
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models.user import User
from ..schemas.user import WxLoginRequest, TokenResponse, UserInfo
from ..utils.auth import create_token, get_current_user

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=TokenResponse)
async def wx_login(req: WxLoginRequest, db: Session = Depends(get_db)):
    """微信小程序登录: code 换 openid → 创建/更新用户 → 返回 JWT"""
    # 调用微信接口获取 openid
    openid = await _get_openid(req.code)

    # 查找或创建用户
    user = db.query(User).filter(User.openid == openid).first()
    if not user:
        # 第一个注册的用户自动成为管理员（软件开发者）
        is_first = db.query(User).count() == 0
        user = User(
            openid=openid,
            nickname=req.nickname or "知问用户",
            avatar_url=req.avatar_url,
            is_admin=is_first,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        if req.nickname:
            user.nickname = req.nickname
        if req.avatar_url:
            user.avatar_url = req.avatar_url
        db.commit()
        db.refresh(user)

    token = create_token(user.id)
    return TokenResponse(
        token=token,
        user_id=user.id,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
    )


@router.get("/me", response_model=UserInfo)
def get_me(user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return user


async def _get_openid(code: str) -> str:
    """微信 code2Session 接口"""
    if not settings.wechat_app_id or settings.wechat_app_id == "your_app_id_here":
        # 开发模式: 直接用 code 作为 openid (方便调试)
        return f"dev_{code}"

    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": settings.wechat_app_id,
        "secret": settings.wechat_app_secret,
        "js_code": code,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        data = resp.json()

    if "openid" not in data:
        raise HTTPException(status_code=400, detail=f"微信登录失败: {data.get('errmsg', '未知错误')}")
    return data["openid"]
