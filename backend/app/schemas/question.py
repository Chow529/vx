from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class QuestionCreate(BaseModel):
    title: str
    content: str
    answer: str = ""
    tech_stack: str = "其他"
    difficulty: int = 1
    tags: List[str] = []


class QuestionUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    answer: Optional[str] = None
    tech_stack: Optional[str] = None
    difficulty: Optional[int] = None
    mastery: Optional[int] = None
    tags: Optional[List[str]] = None


class QuestionOut(BaseModel):
    id: int
    title: str
    content: str
    answer: str
    tech_stack: str
    difficulty: int
    mastery: int
    source: str
    is_archived: bool
    tags: List[str] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class QuestionListOut(BaseModel):
    total: int
    items: List[QuestionOut]


class ParsedQA(BaseModel):
    """文件解析后的 QA 对"""
    question: str
    answer: str = ""
    tech_stack: str = "其他"
    difficulty: int = 1


class FileParseResult(BaseModel):
    filename: str
    items: List[ParsedQA]


class CollectFromPost(BaseModel):
    """从社区收藏题目"""
    post_id: int
    difficulty: int = 1
