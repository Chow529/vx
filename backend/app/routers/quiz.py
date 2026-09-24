"""大模型出题路由"""
import random
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.user import User
from ..models.question import Question, PublicQuestion
from ..schemas.public_question import QuizGenerateRequest, QuizOut, QuizQuestion
from ..services.ai_service import generate_quiz_questions
from ..utils.auth import get_current_user

router = APIRouter(prefix="/quiz", tags=["大模型出题"])


@router.post("/generate", response_model=QuizOut)
def generate_quiz(
    data: QuizGenerateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    大模型出题
    source: "all" = 从公共题库 + 个人题库选题
            "my_questions" = 仅从个人题库选题
    """
    # 验证题目数量
    if data.count < 10:
        raise HTTPException(status_code=400, detail="题目数量最少为 10 题")
    
    questions = []
    
    if data.source == "my_questions":
        # 仅从个人题库选题
        q = db.query(Question).filter(
            Question.user_id == user.id,
            Question.is_archived == False
        )
        if data.tech_stack:
            q = q.filter(Question.tech_stack == data.tech_stack)
        if data.difficulty:
            q = q.filter(Question.difficulty == data.difficulty)
        questions = q.all()
    else:
        # 从公共题库 + 个人题库选题
        personal_q = db.query(Question).filter(
            Question.user_id == user.id,
            Question.is_archived == False
        )
        if data.tech_stack:
            personal_q = personal_q.filter(Question.tech_stack == data.tech_stack)
        if data.difficulty:
            personal_q = personal_q.filter(Question.difficulty == data.difficulty)
        
        public_q = db.query(PublicQuestion)
        if data.tech_stack:
            public_q = public_q.filter(PublicQuestion.tech_stack == data.tech_stack)
        if data.difficulty:
            public_q = public_q.filter(PublicQuestion.difficulty == data.difficulty)
        
        questions = personal_q.all() + public_q.all()
    
    if not questions:
        raise HTTPException(status_code=400, detail="没有找到符合条件的题目")
    
    # 随机选择题目（题库不足时返回全部）
    actual_count = min(data.count, len(questions))
    selected = random.sample(questions, actual_count)
    
    # 使用大模型生成答题选项和解析
    quiz_questions = generate_quiz_questions(selected)
    
    return QuizOut(questions=quiz_questions, total=len(quiz_questions))
