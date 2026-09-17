from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class PublicQuestionCreate(BaseModel):
    title: str
    content: str
    answer: str = ""
    tech_stack: str = "其他"
    difficulty: int = 1


class PublicQuestionUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    answer: Optional[str] = None
    tech_stack: Optional[str] = None
    difficulty: Optional[int] = None


class PublicQuestionOut(BaseModel):
    id: int
    user_id: int
    title: str
    content: str
    answer: str
    tech_stack: str
    difficulty: int
    view_count: int
    comment_count: int
    user_nickname: str = ""
    user_avatar: str = ""
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PublicQuestionListOut(BaseModel):
    total: int
    items: List[PublicQuestionOut]


class PublicCommentCreate(BaseModel):
    content: str


class PublicCommentOut(BaseModel):
    id: int
    question_id: int
    user_id: int
    content: str
    user_nickname: str = ""
    user_avatar: str = ""
    created_at: datetime

    class Config:
        from_attributes = True


# Quiz schemas
class QuizGenerateRequest(BaseModel):
    count: int = 5
    tech_stack: Optional[str] = None
    difficulty: Optional[int] = None
    source: str = "all"  # all / my_questions


class QuizQuestion(BaseModel):
    id: int
    question: str
    options: List[str] = []
    correct_answer: str
    explanation: str = ""
    tech_stack: str = ""
    difficulty: int = 1


class QuizOut(BaseModel):
    questions: List[QuizQuestion]
    total: int
