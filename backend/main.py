"""FastAPI 主入口"""
import os
import sys
import logging

# 配置日志级别 - 屏蔽调试信息
logging.basicConfig(level=logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("fastapi").setLevel(logging.WARNING)

# 确保 data 目录存在
os.makedirs("data", exist_ok=True)
#os.makedirs("uploads", exist_ok=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.routers import auth, question, post, public_question, quiz

# 建表
Base.metadata.create_all(bind=engine)


def _backfill_vectors():
    """补齐缺失的题目向量（历史数据 / 之前 ollama 不可用时漏掉的）

    在后台线程执行，不阻塞启动；ollama 不可用时静默跳过，下次启动再试。
    """
    from app.database import SessionLocal
    from app.models import Question
    from app.services import vector_service

    if not vector_service.is_available():
        print("[向量库] ollama embedding 不可用，跳过向量补齐", flush=True)
        return

    db = SessionLocal()
    try:
        rows = db.query(Question.id, Question.title, Question.content).all()
        if not rows:
            return
        have = vector_service.indexed_ids()
        missing = [(qid, f"{title}\n{content or ''}") for qid, title, content in rows if qid not in have]
        if not missing:
            print(f"[向量库] 索引完整（{len(have)} 条），无需补齐", flush=True)
            return

        print(f"[向量库] 待补齐 {len(missing)} 条（已有 {len(have)} 条）...", flush=True)
        if not have:
            # 索引为空：一次性全量重建，只写一次磁盘
            vector_service.rebuild_index(missing)
            ok = len(vector_service.indexed_ids())
        else:
            # 少量缺失：逐条追加
            ok = sum(1 for qid, text in missing if vector_service.add_question(qid, text))
        print(f"[向量库] 补齐完成：成功 {ok}/{len(missing)} 条，索引共 {len(vector_service.indexed_ids())} 条", flush=True)
    except Exception as e:
        print(f"[向量库] 补齐失败：{e}", flush=True)
    finally:
        db.close()


def _run_migrations():
    """为已存在的表补新增字段（轻量迁移，兼容 SQLite / MySQL）"""
    from sqlalchemy import text, inspect

    inspector = inspect(engine)
    add_columns = {
        "users": [("is_admin", "BOOLEAN DEFAULT 0")],
        "questions": [("published_post_id", "INTEGER")],
        "posts": [("answer", "TEXT")],
    }
    with engine.begin() as conn:
        for table, cols in add_columns.items():
            if not inspector.has_table(table):
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for col_name, col_type in cols:
                if col_name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))


_run_migrations()

# 后台线程补齐题目向量，不阻塞服务启动
import threading
threading.Thread(target=_backfill_vectors, daemon=True).start()


app = FastAPI(title="知问库 API", version="1.0.0")

# 跨域 (小程序需要)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix="/api")
app.include_router(question.router, prefix="/api")
app.include_router(post.router, prefix="/api")
app.include_router(public_question.router, prefix="/api")
app.include_router(quiz.router, prefix="/api")


@app.get("/")
def root():
    return {"message": "知问库 API 运行中", "docs": "/docs"}


@app.get("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="192.168.31.138", port=8000, reload=True)