"""FastAPI 主入口"""
import os
import sys
import logging

# 配置日志级别 - 屏蔽调试信息
logging.basicConfig(level=logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("fastapi").setLevel(logging.WARNING)

# HuggingFace 镜像 (国内加速)
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

# 确保 data 目录存在
os.makedirs("data", exist_ok=True)
os.makedirs("uploads", exist_ok=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.routers import auth, question, post, public_question, quiz

# 建表
Base.metadata.create_all(bind=engine)

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
