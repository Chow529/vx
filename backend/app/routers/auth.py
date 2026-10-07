"""用户认证路由"""
import os
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models.user import User
from ..schemas.user import WxLoginRequest, TokenResponse, UserInfo, ProfileUpdate
from ..utils.auth import create_token, get_current_user

router = APIRouter(prefix="/auth", tags=["认证"])

AVATAR_DIR = os.path.join("uploads", "avatars")
ALLOWED_AVATAR_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2MB

# .env 中未填写真实值时的占位符
_PLACEHOLDERS = {"", "your_app_id_here", "your_app_secret_here"}


def wechat_login_configured() -> bool:
    """AppID 与 AppSecret 是否都已填写为真实值

    必须两者都填对才走微信真实登录。只填一个（如本次报错的
    「AppID 已填、AppSecret 仍是占位符」）会去调微信接口被拒，
    此时按未配置处理，回退到开发模式。
    """
    return (
        settings.wechat_app_id not in _PLACEHOLDERS
        and settings.wechat_app_secret not in _PLACEHOLDERS
    )


@router.post("/login", response_model=TokenResponse)
async def wx_login(req: WxLoginRequest, db: Session = Depends(get_db)):
    """微信小程序登录: code 换 openid → 创建/更新用户 → 返回 JWT"""
    # 调用微信接口获取 openid
    openid = await _get_openid(req.code)

    # .env 中 ADMIN_OPENIDS 指定的账号，每次登录都强制同步为管理员，
    # 避免因换环境 / 重装数据库导致管理员身份丢失。
    in_admin_list = openid in settings.admin_openid_set

    # 查找或创建用户
    user = db.query(User).filter(User.openid == openid).first()
    if not user:
        # 兜底：ADMIN_OPENIDS 未配置时，第一个注册的用户自动成为管理员
        is_first = not settings.admin_openid_set and db.query(User).count() == 0
        user = User(
            openid=openid,
            nickname=req.nickname or "知问用户",
            avatar_url=req.avatar_url,
            is_admin=in_admin_list or is_first,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        if req.nickname:
            user.nickname = req.nickname
        if req.avatar_url:
            user.avatar_url = req.avatar_url
        if in_admin_list and not user.is_admin:
            user.is_admin = True
        db.commit()
        db.refresh(user)

    token = create_token(user.id)
    return TokenResponse(
        token=token,
        user_id=user.id,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        is_admin=user.is_admin,
    )


@router.get("/me", response_model=UserInfo)
def get_me(user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return user


@router.put("/profile", response_model=UserInfo)
def update_profile(
    data: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新昵称 / 头像

    微信收回 wx.getUserProfile 后，昵称头像需由用户通过
    「头像昵称填写能力」主动填写，再由前端提交到这里保存。
    """
    if data.nickname is not None:
        nickname = data.nickname.strip()
        if not nickname:
            raise HTTPException(status_code=400, detail="昵称不能为空")
        if len(nickname) > 64:
            raise HTTPException(status_code=400, detail="昵称过长（最多 64 字）")
        user.nickname = nickname
    if data.avatar_url is not None:
        user.avatar_url = data.avatar_url.strip()

    db.commit()
    db.refresh(user)
    return user


@router.post("/avatar")
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    nickname: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传头像图片（可选同时提交昵称）

    文件名固定为 `用户ID.扩展名`，同一用户重复上传直接覆盖旧头像，
    不会在磁盘上堆积垃圾文件。
    微信「头像昵称填写能力」给到的是临时路径，必须转存到服务器，
    否则临时文件失效后头像就显示不出来了。
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_AVATAR_EXT:
        raise HTTPException(status_code=400, detail="仅支持 png / jpg / gif / webp 格式")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(content) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=400, detail="头像不能超过 2MB")

    os.makedirs(AVATAR_DIR, exist_ok=True)

    # 覆盖式保存：先删掉该用户其他扩展名的旧头像，再写新文件
    for old in os.listdir(AVATAR_DIR):
        if old.startswith(f"{user.id}."):
            os.remove(os.path.join(AVATAR_DIR, old))

    filename = f"{user.id}{ext}"
    with open(os.path.join(AVATAR_DIR, filename), "wb") as f:
        f.write(content)

    # 附带版本号，避免覆盖后微信/浏览器仍读旧缓存
    version = int(datetime.now().timestamp())
    url = str(request.base_url).rstrip("/") + f"/static/avatars/{filename}?v={version}"
    user.avatar_url = url

    # 头像与昵称通常一起修改，允许在同一次请求里带上昵称
    if nickname is not None:
        nickname = nickname.strip()
        if nickname and len(nickname) <= 64:
            user.nickname = nickname

    db.commit()
    db.refresh(user)
    return {"ok": True, "avatar_url": url, "nickname": user.nickname}


async def _get_openid(code: str) -> str:
    """微信 code2Session 接口"""
    if not wechat_login_configured():
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
