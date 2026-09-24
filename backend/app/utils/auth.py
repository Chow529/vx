"""JWT 工具 & 微信登录依赖注入"""
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models.user import User

security = HTTPBearer(auto_error=False)


def create_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now() + timedelta(days=settings.jwt_expire_days),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    try:
        payload = jwt.decode(
            creds.credentials, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token 无效")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user


def get_optional_user(
    creds: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """可选登录：token 有效返回用户，否则返回 None（不抛异常）"""
    if not creds:
        return None
    try:
        payload = jwt.decode(
            creds.credentials, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None
    return db.query(User).filter(User.id == user_id).first()


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """要求当前用户为管理员"""
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user


def can_manage(user: User, owner_id: int) -> bool:
    """判断用户是否有权管理某资源：本人或管理员"""
    return user.id == owner_id or user.is_admin

