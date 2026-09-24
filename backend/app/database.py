from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import settings

# SQLite 需要单线程豁免；MySQL 等使用连接池健康检查
connect_args = {}
engine_kwargs = {}

if settings.is_sqlite:
    connect_args["check_same_thread"] = False
    engine_kwargs["connect_args"] = connect_args
else:
    # pool_pre_ping: 取出连接前先探活，避免 MySQL 8 小时闲置断连
    # pool_recycle: 连接回收时间（秒），需小于 MySQL wait_timeout
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = 3600
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
