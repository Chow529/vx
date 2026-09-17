"""社区帖子路由"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.user import User
from ..models.post import Post, Comment, post_tags
from ..models.question import Question, Tag
from ..schemas.post import PostCreate, PostOut, PostListOut, CommentCreate, CommentOut
from ..services import vector_service
from ..utils.auth import get_current_user

router = APIRouter(prefix="/posts", tags=["社区"])


@router.get("/", response_model=PostListOut)
def list_posts(
    sort: str = Query("latest", pattern="^(latest|hot|unsolved)$"),
    tech_stack: Optional[str] = None,
    tag: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """获取社区帖子列表"""
    q = db.query(Post)

    if tech_stack:
        q = q.filter(Post.tech_stack == tech_stack)
    if tag:
        q = q.filter(Post.tags.any(Tag.name == tag))

    if sort == "latest":
        q = q.order_by(Post.created_at.desc())
    elif sort == "hot":
        q = q.order_by((Post.like_count + Post.comment_count * 2).desc())
    elif sort == "unsolved":
        q = q.filter(Post.is_solved == False).order_by(Post.created_at.desc())

    total = q.count()
    items = q.offset((page - 1) * size).limit(size).all()

    return PostListOut(total=total, items=[_post_to_out(p) for p in items])


@router.post("/", response_model=PostOut)
def create_post(
    data: PostCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """发布题目帖"""
    post = Post(
        user_id=user.id,
        title=data.title,
        content=data.content,
        tech_stack=data.tech_stack,
        difficulty=data.difficulty,
    )

    # 打标签
    tag_names = data.tags or []
    if data.tech_stack and data.tech_stack not in tag_names:
        tag_names.append(data.tech_stack)
    tags = []
    for name in tag_names:
        name = name.strip()
        if not name:
            continue
        t = db.query(Tag).filter(Tag.name == name).first()
        if not t:
            t = Tag(name=name)
            db.add(t)
            db.flush()
        tags.append(t)
    post.tags = tags

    db.add(post)
    db.commit()
    db.refresh(post)

    # 同步存入个人题库
    if data.also_save_to_my:
        question = Question(
            user_id=user.id,
            title=post.title,
            content=post.content,
            tech_stack=post.tech_stack,
            difficulty=post.difficulty,
            source="manual",
        )
        question.tags = tags
        db.add(question)
        db.commit()
        db.refresh(question)
        vector_service.add_question(question.id, f"{question.title}\n{question.content}")

    return _post_to_out(post)


@router.get("/{post_id}", response_model=PostOut)
def get_post(post_id: int, db: Session = Depends(get_db)):
    """获取帖子详情"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    return _post_to_out(post)


@router.delete("/{post_id}")
def delete_post(
    post_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除帖子 (仅作者)"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    if post.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权删除")
    db.delete(post)
    db.commit()
    return {"ok": True}


@router.post("/{post_id}/like")
def like_post(
    post_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """点赞"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    post.like_count += 1
    db.commit()
    return {"ok": True, "like_count": post.like_count}


@router.get("/{post_id}/comments", response_model=list[CommentOut])
def list_comments(post_id: int, db: Session = Depends(get_db)):
    """获取帖子评论 (含楼中楼)"""
    # 只查顶级评论
    top_comments = db.query(Comment).filter(
        Comment.post_id == post_id, Comment.parent_id.is_(None)
    ).order_by(Comment.created_at.asc()).all()

    result = []
    for c in top_comments:
        out = _comment_to_out(c)
        # 加载子回复
        if c.replies:
            out.replies = [_comment_to_out(r) for r in c.replies]
        result.append(out)
    return result


@router.post("/{post_id}/comments", response_model=CommentOut)
def create_comment(
    post_id: int,
    data: CommentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """发表评论 / 楼中楼回复"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    comment = Comment(
        post_id=post_id,
        user_id=user.id,
        content=data.content,
        parent_id=data.parent_id,
    )
    db.add(comment)
    post.comment_count += 1
    db.commit()
    db.refresh(comment)
    return _comment_to_out(comment)


@router.post("/{post_id}/comments/{comment_id}/adopt")
def adopt_answer(
    post_id: int,
    comment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """采纳最佳答案 (仅楼主可操作)"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    if post.user_id != user.id:
        raise HTTPException(status_code=403, detail="只有楼主可以采纳")

    comment = db.query(Comment).filter(Comment.id == comment_id, Comment.post_id == post_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")

    comment.is_adopted = True
    post.is_solved = True
    # 被采纳者获得声望
    comment.user.reputation += 10
    db.commit()
    return {"ok": True}


@router.post("/{post_id}/comments/{comment_id}/like")
def like_comment(
    post_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
):
    """评论点赞"""
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")
    comment.like_count += 1
    db.commit()
    return {"ok": True, "like_count": comment.like_count}


# ─── 辅助函数 ───

def _post_to_out(p: Post) -> PostOut:
    return PostOut(
        id=p.id,
        title=p.title,
        content=p.content,
        images=p.images or "",
        tech_stack=p.tech_stack,
        difficulty=p.difficulty,
        is_solved=p.is_solved,
        like_count=p.like_count,
        comment_count=p.comment_count,
        created_at=p.created_at,
        user_nickname=p.user.nickname if p.user else "",
        user_avatar=p.user.avatar_url if p.user else "",
        tags=[t.name for t in p.tags],
    )


def _comment_to_out(c: Comment) -> CommentOut:
    return CommentOut(
        id=c.id,
        post_id=c.post_id,
        content=c.content,
        parent_id=c.parent_id,
        is_adopted=c.is_adopted,
        like_count=c.like_count,
        created_at=c.created_at,
        user_nickname=c.user.nickname if c.user else "",
        user_avatar=c.user.avatar_url if c.user else "",
    )
