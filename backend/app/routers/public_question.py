"""公共题库路由"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.user import User
from ..models.question import PublicQuestion
from ..models.public_question import PublicComment
from ..schemas.public_question import (
    PublicQuestionCreate, PublicQuestionUpdate, PublicQuestionOut,
    PublicQuestionListOut, PublicCommentCreate, PublicCommentOut,
)
from ..utils.auth import get_current_user

router = APIRouter(prefix="/public-questions", tags=["公共题库"])


@router.get("/", response_model=PublicQuestionListOut)
def list_public_questions(
    tech_stack: Optional[str] = None,
    difficulty: Optional[int] = None,
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """获取公共题库列表"""
    q = db.query(PublicQuestion)

    if tech_stack:
        q = q.filter(PublicQuestion.tech_stack == tech_stack)
    if difficulty is not None:
        q = q.filter(PublicQuestion.difficulty == difficulty)
    if keyword:
        q = q.filter(
            PublicQuestion.title.contains(keyword) |
            PublicQuestion.content.contains(keyword)
        )

    total = q.count()
    items = q.order_by(PublicQuestion.created_at.desc()).offset((page - 1) * size).limit(size).all()

    return PublicQuestionListOut(total=total, items=[_public_q_to_out(item) for item in items])


@router.post("/", response_model=PublicQuestionOut)
def create_public_question(
    data: PublicQuestionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传题目到公共题库"""
    question = PublicQuestion(
        user_id=user.id,
        title=data.title,
        content=data.content,
        answer=data.answer,
        tech_stack=data.tech_stack,
        difficulty=data.difficulty,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return _public_q_to_out(question)


@router.get("/{question_id}", response_model=PublicQuestionOut)
def get_public_question(
    question_id: int,
    db: Session = Depends(get_db),
):
    """获取公共题目详情（增加浏览计数）"""
    question = db.query(PublicQuestion).filter(PublicQuestion.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")
    
    question.view_count += 1
    db.commit()
    db.refresh(question)
    return _public_q_to_out(question)


@router.put("/{question_id}", response_model=PublicQuestionOut)
def update_public_question(
    question_id: int,
    data: PublicQuestionUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """编辑公共题目（仅上传者）"""
    question = db.query(PublicQuestion).filter(PublicQuestion.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")
    if question.user_id != user.id:
        raise HTTPException(status_code=403, detail="只有上传者可以编辑")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(question, field, value)

    db.commit()
    db.refresh(question)
    return _public_q_to_out(question)


@router.delete("/{question_id}")
def delete_public_question(
    question_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除公共题目（仅上传者）"""
    question = db.query(PublicQuestion).filter(PublicQuestion.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")
    if question.user_id != user.id:
        raise HTTPException(status_code=403, detail="只有上传者可以删除")

    db.delete(question)
    db.commit()
    return {"ok": True}


@router.get("/{question_id}/comments", response_model=list[PublicCommentOut])
def list_comments(question_id: int, db: Session = Depends(get_db)):
    """获取题目评论"""
    question = db.query(PublicQuestion).filter(PublicQuestion.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")
    
    comments = db.query(PublicComment).filter(PublicComment.question_id == question_id).order_by(PublicComment.created_at.asc()).all()
    return [_comment_to_out(c) for c in comments]


@router.post("/{question_id}/comments", response_model=PublicCommentOut)
def create_comment(
    question_id: int,
    data: PublicCommentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """发表评论"""
    question = db.query(PublicQuestion).filter(PublicQuestion.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    comment = PublicComment(
        question_id=question_id,
        user_id=user.id,
        content=data.content,
    )
    db.add(comment)
    question.comment_count += 1
    db.commit()
    db.refresh(comment)
    return _comment_to_out(comment)


@router.delete("/{question_id}/comments/{comment_id}")
def delete_comment(
    question_id: int,
    comment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除评论（仅上传者）"""
    comment = db.query(PublicComment).filter(PublicComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")
    if comment.user_id != user.id:
        raise HTTPException(status_code=403, detail="只有评论者可以删除")

    # 更新题目的评论计数
    question = db.query(PublicQuestion).filter(PublicQuestion.id == question_id).first()
    if question:
        question.comment_count = max(0, question.comment_count - 1)

    db.delete(comment)
    db.commit()
    return {"ok": True}


# ─── 辅助函数 ───

def _public_q_to_out(q: PublicQuestion) -> PublicQuestionOut:
    return PublicQuestionOut(
        id=q.id,
        user_id=q.user_id,
        title=q.title,
        content=q.content,
        answer=q.answer,
        tech_stack=q.tech_stack,
        difficulty=q.difficulty,
        view_count=q.view_count,
        comment_count=q.comment_count,
        user_nickname=q.user.nickname if q.user else "",
        user_avatar=q.user.avatar_url if q.user else "",
        created_at=q.created_at,
        updated_at=q.updated_at,
    )


def _comment_to_out(c: PublicComment) -> PublicCommentOut:
    return PublicCommentOut(
        id=c.id,
        question_id=c.question_id,
        user_id=c.user_id,
        content=c.content,
        user_nickname=c.user.nickname if c.user else "",
        user_avatar=c.user.avatar_url if c.user else "",
        created_at=c.created_at,
    )
