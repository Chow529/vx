"""社区帖子路由"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.user import User
from ..models.post import Post, Comment, post_tags, post_likes, comment_likes
from ..models.question import Question, Tag
from ..schemas.post import (
    PostCreate, PostUpdate, PostOut, PostListOut,
    CommentCreate, CommentOut,
)
from ..services import vector_service
from ..services.moderation_service import check_content
from ..utils.auth import get_current_user, get_optional_user, can_manage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/posts", tags=["社区"])


def _liked_post_ids(db: Session, user_id: int) -> set:
    """当前用户点赞过的帖子 ID 集合"""
    rows = db.query(post_likes.c.post_id).filter(post_likes.c.user_id == user_id).all()
    return {r[0] for r in rows}


def _liked_comment_ids(db: Session, user_id: int) -> set:
    """当前用户点赞过的评论 ID 集合"""
    rows = db.query(comment_likes.c.comment_id).filter(comment_likes.c.user_id == user_id).all()
    return {r[0] for r in rows}


def _collected_post_ids(db: Session, user_id: int) -> set:
    """当前用户题库中已包含的帖子 ID 集合

    两类来源都算「已在题库」：
      1. 从社区收藏的（source=community, source_post_id）
      2. 自己发布时勾选存入 / 从题库发布到社区的（published_post_id）
    """
    rows = db.query(Question.source_post_id).filter(
        Question.user_id == user_id,
        Question.source == "community",
        Question.source_post_id.isnot(None),
    ).all()
    ids = {r[0] for r in rows}

    rows = db.query(Question.published_post_id).filter(
        Question.user_id == user_id,
        Question.published_post_id.isnot(None),
    ).all()
    ids |= {r[0] for r in rows}
    return ids


@router.get("/", response_model=PostListOut)
def list_posts(
    sort: str = Query("latest", pattern="^(latest|hot)$"),
    mine: bool = Query(False, description="只看当前用户自己发布的帖子"),
    tech_stack: Optional[str] = None,
    tag: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """获取社区帖子列表"""
    q = db.query(Post)

    # 「我的」标签：只看自己发布的（未登录则为空）
    if mine:
        if not current_user:
            return PostListOut(total=0, items=[])
        q = q.filter(Post.user_id == current_user.id)

    if tech_stack:
        q = q.filter(Post.tech_stack == tech_stack)
    if tag:
        q = q.filter(Post.tags.any(Tag.name == tag))

    if sort == "latest":
        q = q.order_by(Post.created_at.desc())
    elif sort == "hot":
        q = q.order_by((Post.like_count + Post.comment_count * 2).desc())

    total = q.count()
    items = q.offset((page - 1) * size).limit(size).all()

    # 当前用户的点赞 / 收藏状态（未登录则为空集合）
    if current_user:
        liked_ids = _liked_post_ids(db, current_user.id)
        collected_ids = _collected_post_ids(db, current_user.id)
    else:
        liked_ids = collected_ids = set()

    return PostListOut(
        total=total,
        items=[_post_to_out(p, current_user, liked_ids, collected_ids) for p in items],
    )


@router.post("/", response_model=PostOut)
def create_post(
    data: PostCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """发布题目帖"""
    # 内容审查
    for field, value in [("标题", data.title), ("内容", data.content), ("答案", data.answer)]:
        result = check_content(value)
        if not result["ok"]:
            logger.warning(f"帖子{field}审查未通过：{result['reason']}")
            raise HTTPException(status_code=400, detail="含有违规内容")

    post = Post(
        user_id=user.id,
        title=data.title,
        content=data.content,
        answer=data.answer,
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

    # 勾选「同时存入我的题库」才入库；未勾选时该帖在社区可被自己收藏
    if data.also_save_to_my:
        question = Question(
            user_id=user.id,
            title=post.title,
            content=post.content,
            answer=post.answer or "",
            tech_stack=post.tech_stack,
            difficulty=post.difficulty,
            source="manual",
            published_post_id=post.id,
        )
        question.tags = tags
        db.add(question)
        db.commit()
        db.refresh(question)
        vector_service.add_question(question.id, f"{question.title}\n{question.content}")

    return _post_to_out(
        post,
        user,
        collected_ids={post.id} if data.also_save_to_my else set(),
    )


@router.get("/{post_id}", response_model=PostOut)
def get_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """获取帖子详情"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    if current_user:
        liked_ids = _liked_post_ids(db, current_user.id)
        collected_ids = _collected_post_ids(db, current_user.id)
    else:
        liked_ids = collected_ids = set()

    return _post_to_out(post, current_user, liked_ids, collected_ids)


@router.delete("/{post_id}")
def delete_post(
    post_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除帖子 (作者或管理员)"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    if not can_manage(user, post.user_id):
        raise HTTPException(status_code=403, detail="无权删除")
    db.delete(post)
    db.commit()
    return {"ok": True}


@router.put("/{post_id}", response_model=PostOut)
def update_post(
    post_id: int,
    data: PostUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """编辑帖子 (作者或管理员)"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    if not can_manage(user, post.user_id):
        raise HTTPException(status_code=403, detail="无权编辑")

    # 内容审查
    for field, value in [("标题", data.title), ("内容", data.content), ("答案", data.answer)]:
        if value is None:
            continue
        result = check_content(value)
        if not result["ok"]:
            logger.warning(f"帖子{field}审查未通过：{result['reason']}")
            raise HTTPException(status_code=400, detail="含有违规内容")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(post, field, value)
    db.commit()
    db.refresh(post)
    return _post_to_out(post, user)


@router.post("/{post_id}/like")
def like_post(
    post_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """点赞 / 取消点赞（切换）"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    already = db.query(post_likes).filter(
        (post_likes.c.post_id == post_id) & (post_likes.c.user_id == user.id)
    ).first() is not None

    if already:
        # 取消点赞
        db.execute(
            post_likes.delete().where(
                (post_likes.c.post_id == post_id) & (post_likes.c.user_id == user.id)
            )
        )
        post.like_count = max(0, post.like_count - 1)
        liked = False
    else:
        # 点赞
        db.execute(post_likes.insert().values(post_id=post_id, user_id=user.id))
        post.like_count += 1
        liked = True

    db.commit()
    return {"ok": True, "liked": liked, "like_count": post.like_count}


@router.get("/{post_id}/comments", response_model=list[CommentOut])
def list_comments(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """获取帖子评论 (含楼中楼)"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    # 只查顶级评论
    top_comments = db.query(Comment).filter(
        Comment.post_id == post_id, Comment.parent_id.is_(None)
    ).order_by(Comment.created_at.asc()).all()

    liked_ids = _liked_comment_ids(db, current_user.id) if current_user else set()

    def _can(c: Comment) -> bool:
        # 评论作者、楼主、管理员可删除
        return bool(current_user and can_manage(current_user, c.user_id)) or bool(
            current_user and current_user.id == post.user_id
        )

    result = []
    for c in top_comments:
        out = _comment_to_out(c, liked_ids, _can(c))
        # 加载子回复
        if c.replies:
            out.replies = [_comment_to_out(r, liked_ids, _can(r)) for r in c.replies]
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

    # 内容审查
    result = check_content(data.content)
    if not result["ok"]:
        logger.warning(f"评论审查未通过：{result['reason']}")
        raise HTTPException(status_code=400, detail="含有违规内容")

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


@router.delete("/{post_id}/comments/{comment_id}")
def delete_comment(
    post_id: int,
    comment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除评论 (评论作者、帖子作者或管理员)"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    comment = db.query(Comment).filter(Comment.id == comment_id, Comment.post_id == post_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")

    # 评论作者、帖子楼主、管理员均可删除
    if not (can_manage(user, comment.user_id) or user.id == post.user_id):
        raise HTTPException(status_code=403, detail="无权删除该评论")

    db.delete(comment)
    post.comment_count = max(0, post.comment_count - 1)
    db.commit()
    return {"ok": True}


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
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """评论点赞 / 取消点赞（切换）"""
    comment = db.query(Comment).filter(
        Comment.id == comment_id, Comment.post_id == post_id
    ).first()
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")

    already = db.query(comment_likes).filter(
        (comment_likes.c.comment_id == comment_id) & (comment_likes.c.user_id == user.id)
    ).first() is not None

    if already:
        db.execute(
            comment_likes.delete().where(
                (comment_likes.c.comment_id == comment_id) & (comment_likes.c.user_id == user.id)
            )
        )
        comment.like_count = max(0, comment.like_count - 1)
        liked = False
    else:
        db.execute(comment_likes.insert().values(comment_id=comment_id, user_id=user.id))
        comment.like_count += 1
        liked = True

    db.commit()
    return {"ok": True, "liked": liked, "like_count": comment.like_count}


# ─── 辅助函数 ───

def _post_to_out(
    p: Post,
    current_user: Optional[User] = None,
    liked_ids: Optional[set] = None,
    collected_ids: Optional[set] = None,
) -> PostOut:
    return PostOut(
        id=p.id,
        user_id=p.user_id,
        title=p.title,
        content=p.content,
        answer=p.answer or "",
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
        is_liked=bool(liked_ids and p.id in liked_ids),
        is_collected=bool(collected_ids and p.id in collected_ids),
        is_own=bool(current_user and p.user_id == current_user.id),
        can_manage=bool(current_user and can_manage(current_user, p.user_id)),
    )


def _comment_to_out(c: Comment, liked_ids: Optional[set] = None, can_delete: bool = False) -> CommentOut:
    return CommentOut(
        id=c.id,
        post_id=c.post_id,
        user_id=c.user_id,
        content=c.content,
        parent_id=c.parent_id,
        is_adopted=c.is_adopted,
        like_count=c.like_count,
        created_at=c.created_at,
        user_nickname=c.user.nickname if c.user else "",
        user_avatar=c.user.avatar_url if c.user else "",
        is_liked=bool(liked_ids and c.id in liked_ids),
        can_delete=can_delete,
    )
