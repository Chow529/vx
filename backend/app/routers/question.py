"""个人题库路由"""
import logging
from datetime import datetime, time as dtime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.user import User
from ..models.question import Question, Tag, question_tags
from ..schemas.question import (
    QuestionCreate, QuestionUpdate, QuestionOut, QuestionListOut,
    FileParseResult, ParsedQA, CollectFromPost,
)
from ..models.post import Post, Comment, post_likes
from ..services import vector_service
from ..services.ai_service import analyze_question
from ..services.moderation_service import check_content
from ..utils.auth import get_current_user
from ..utils.parser import parse_file

logger = logging.getLogger(__name__)

# 每人每天最多收藏数量
DAILY_COLLECT_LIMIT = 10

router = APIRouter(prefix="/questions", tags=["题库"])


@router.get("/", response_model=QuestionListOut)
def list_questions(
    tech_stack: Optional[str] = None,
    difficulty: Optional[int] = None,
    mastery: Optional[int] = None,
    archived: bool = False,
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取个人题库列表, 支持多维度筛选"""
    q = db.query(Question).filter(Question.user_id == user.id, Question.is_archived == archived)

    if tech_stack:
        q = q.filter(Question.tech_stack == tech_stack)
    if difficulty is not None:
        q = q.filter(Question.difficulty == difficulty)
    if mastery is not None:
        q = q.filter(Question.mastery == mastery)
    if keyword:
        # 语义搜索
        results = vector_service.search_similar(keyword, top_k=50)
        if results:
            qids = [r["question_id"] for r in results]
            q = q.filter(Question.id.in_(qids))
        else:
            # 降级为关键词搜索
            q = q.filter(Question.title.contains(keyword) | Question.content.contains(keyword))

    total = q.count()
    items = q.order_by(Question.created_at.desc()).offset((page - 1) * size).limit(size).all()

    return QuestionListOut(
        total=total,
        items=[_question_to_out(item) for item in items],
    )


@router.post("/", response_model=QuestionOut)
def create_question(
    data: QuestionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """手动录入题目"""
    question = Question(
        user_id=user.id,
        title=data.title,
        content=data.content,
        answer=data.answer,
        tech_stack=data.tech_stack,
        difficulty=data.difficulty,
        source="manual",
    )
    _apply_tags(question, data.tags, db)
    db.add(question)
    db.commit()
    db.refresh(question)

    # 向量化
    vector_service.add_question(question.id, f"{question.title}\n{question.content}")

    return _question_to_out(question)


@router.get("/tech-stacks")
def list_tech_stacks():
    """获取技术栈分类列表"""
    return {"stacks": TECH_STACKS}


@router.get("/{question_id}", response_model=QuestionOut)
def get_question(
    question_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取题目详情"""
    question = _get_user_question(question_id, user.id, db)
    return _question_to_out(question)


@router.put("/{question_id}", response_model=QuestionOut)
def update_question(
    question_id: int,
    data: QuestionUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新题目"""
    question = _get_user_question(question_id, user.id, db)

    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "tags":
            _apply_tags(question, value, db)
        else:
            setattr(question, field, value)

    db.commit()
    db.refresh(question)

    # 更新向量
    vector_service.remove_question(question.id)
    vector_service.add_question(question.id, f"{question.title}\n{question.content}")

    return _question_to_out(question)


@router.delete("/{question_id}")
def delete_question(
    question_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除题目（若已发布社区，同步删除对应帖子及其评论、点赞）"""
    question = _get_user_question(question_id, user.id, db)

    # 级联删除已发布的社区帖子
    if question.published_post_id:
        _delete_post_cascade(question.published_post_id, db)

    vector_service.remove_question(question.id)
    db.delete(question)
    db.commit()
    return {"ok": True}


def _delete_post_cascade(post_id: int, db: Session):
    """删除帖子并清理其评论、点赞关联（不 commit，供复用）"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return
    db.query(Comment).filter(Comment.post_id == post_id).delete(synchronize_session=False)
    db.execute(post_likes.delete().where(post_likes.c.post_id == post_id))
    db.delete(post)


@router.post("/{question_id}/mastery")
def set_mastery(
    question_id: int,
    mastery: int = Query(..., ge=0, le=2),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """设置掌握程度 (0=未掌握, 1=学习中, 2=已掌握)"""
    question = _get_user_question(question_id, user.id, db)
    question.mastery = mastery
    # 已掌握 → 自动归档
    if mastery == 2:
        question.is_archived = True
    db.commit()
    return {"ok": True, "mastery": mastery, "is_archived": question.is_archived}


@router.post("/batch-mastery")
def batch_set_mastery(
    question_ids: list[int],
    mastery: int = Query(..., ge=0, le=2),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """批量设置掌握程度"""
    questions = db.query(Question).filter(
        Question.id.in_(question_ids), Question.user_id == user.id
    ).all()
    for q in questions:
        q.mastery = mastery
        if mastery == 2:
            q.is_archived = True
    db.commit()
    return {"ok": True, "count": len(questions)}


@router.post("/upload", response_model=FileParseResult)
async def upload_and_parse(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """上传文件并解析为 QA 对，通过 AI 自动判断技术栈和难度"""
    logger.info(f"文件上传接口被调用，用户 ID: {user.id}")
    
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件为空")

    logger.info(f"文件大小：{len(content) / 1024:.2f} KB，文件名：{file.filename}")
    
    try:
        items = parse_file(file.filename or "unknown", content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 通过 AI 批量分析每道题的技术栈和难度
    from ..schemas.question import ParsedQA
    from ..services.ai_service import analyze_batch
    
    logger.info(f"开始 AI 分析 {len(items)} 道题...")
    
    # 准备批量分析的数据
    qa_list = [{"question": item.question, "answer": item.answer} for item in items]
    analyses = analyze_batch(qa_list)
    
    # 构建结果
    analyzed_items = []
    for item, analysis in zip(items, analyses):
        analyzed_items.append(ParsedQA(
            question=item.question,
            answer=item.answer,
            tech_stack=analysis["tech_stack"],
            difficulty=analysis["difficulty"],
        ))

    logger.info(f"文件解析和 AI 分析完成，共 {len(analyzed_items)} 道题")

    return FileParseResult(filename=file.filename or "unknown", items=analyzed_items)


@router.post("/import")
def import_questions(
    items: list[QuestionCreate],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """批量导入解析后的 QA 对到题库"""
    created = []
    for item in items:
        question = Question(
            user_id=user.id,
            title=item.title,
            content=item.content,
            answer=item.answer,
            tech_stack=item.tech_stack,
            difficulty=item.difficulty,
            source="file_import",
        )
        _apply_tags(question, item.tags, db)
        db.add(question)
        db.flush()
        vector_service.add_question(question.id, f"{question.title}\n{question.content}")
        created.append(question.id)

    db.commit()
    return {"ok": True, "count": len(created), "ids": created}


@router.post("/collect/{post_id}")
def collect_from_post(
    post_id: int,
    data: CollectFromPost,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """从社区收藏题目到个人题库（切换：已收藏则取消）"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    # 自己发布时已勾选存入题库的，无需重复收藏
    own_saved = db.query(Question).filter(
        Question.user_id == user.id,
        Question.published_post_id == post_id,
    ).first()
    if own_saved:
        raise HTTPException(status_code=400, detail="该题目已在你的题库中")

    # 已收藏则取消
    existing = db.query(Question).filter(
        Question.user_id == user.id,
        Question.source == "community",
        Question.source_post_id == post_id,
    ).first()
    if existing:
        vector_service.remove_question(existing.id)
        db.delete(existing)
        db.commit()
        return {"ok": True, "collected": False}

    # 每天最多收藏 10 题
    today_start = datetime.combine(datetime.now().date(), dtime.min)
    collected_today = db.query(Question).filter(
        Question.user_id == user.id,
        Question.source == "community",
        Question.created_at >= today_start,
    ).count()
    if collected_today >= DAILY_COLLECT_LIMIT:
        raise HTTPException(status_code=400, detail=f"每天最多收藏 {DAILY_COLLECT_LIMIT} 个题目")

    question = Question(
        user_id=user.id,
        title=post.title,
        content=post.content,
        answer=post.answer or "",
        tech_stack=post.tech_stack,
        difficulty=data.difficulty,
        source="community",
        source_post_id=post_id,
    )
    tag_names = [t.name for t in post.tags]
    _apply_tags(question, tag_names, db)
    db.add(question)
    db.commit()
    db.refresh(question)

    vector_service.add_question(question.id, f"{question.title}\n{question.content}")
    remaining = DAILY_COLLECT_LIMIT - collected_today - 1
    return {"ok": True, "collected": True, "question_id": question.id, "remaining_today": remaining}


@router.post("/{question_id}/publish", response_model=QuestionOut)
def publish_to_community(
    question_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """将个人题目发布到社区（已发布则拒绝，需先撤销）"""
    question = _get_user_question(question_id, user.id, db)

    # 防重复发布
    if question.published_post_id:
        existing = db.query(Post).filter(Post.id == question.published_post_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="该题目已发布到社区，请先撤销后再发布")
        else:
            # 帖子已被删除，清理脏数据
            question.published_post_id = None

    # 内容审查
    for field, value in [("标题", question.title), ("内容", question.content)]:
        result = check_content(value)
        if not result["ok"]:
            logger.warning(f"发布社区{field}审查未通过：{result['reason']}")
            raise HTTPException(status_code=400, detail="含有违规内容")

    post = Post(
        user_id=user.id,
        title=question.title,
        content=question.content,
        answer=question.answer or "",
        tech_stack=question.tech_stack,
        difficulty=question.difficulty,
    )
    tag_names = [t.name for t in question.tags]
    tags = []
    for name in tag_names:
        t = db.query(Tag).filter(Tag.name == name).first()
        if not t:
            t = Tag(name=name)
            db.add(t)
            db.flush()
        tags.append(t)
    post.tags = tags

    db.add(post)
    db.flush()
    question.published_post_id = post.id
    db.commit()
    db.refresh(question)
    return _question_to_out(question)


@router.post("/{question_id}/withdraw", response_model=QuestionOut)
def withdraw_from_community(
    question_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """从社区撤销已发布的题目（删除对应帖子及其评论、点赞）"""
    question = _get_user_question(question_id, user.id, db)

    if not question.published_post_id:
        raise HTTPException(status_code=400, detail="该题目尚未发布")

    _delete_post_cascade(question.published_post_id, db)
    question.published_post_id = None
    db.commit()
    db.refresh(question)
    return _question_to_out(question)


@router.get("/stats/overview")
def get_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取题库统计数据"""
    base = db.query(Question).filter(Question.user_id == user.id)
    total = base.filter(Question.is_archived == False).count()
    archived = base.filter(Question.is_archived == True).count()

    # 按技术栈分布
    from sqlalchemy import func
    tech_dist = dict(
        db.query(Question.tech_stack, func.count(Question.id))
        .filter(Question.user_id == user.id, Question.is_archived == False)
        .group_by(Question.tech_stack).all()
    )

    # 按掌握程度分布
    mastery_dist = dict(
        db.query(Question.mastery, func.count(Question.id))
        .filter(Question.user_id == user.id, Question.is_archived == False)
        .group_by(Question.mastery).all()
    )

    # 按难度分布
    diff_dist = dict(
        db.query(Question.difficulty, func.count(Question.id))
        .filter(Question.user_id == user.id, Question.is_archived == False)
        .group_by(Question.difficulty).all()
    )

    return {
        "total": total,
        "archived": archived,
        "tech_distribution": tech_dist,
        "mastery_distribution": mastery_dist,
        "difficulty_distribution": diff_dist,
    }


# ─── 技术栈分类 ───

TECH_STACKS = [
    # 编程语言 & 基础
    "Python", "Java", "Go", "C/C++", "Rust", "JavaScript", "TypeScript",
    "C#", "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R",
    # 前端
    "React", "Vue", "Angular", "HTML/CSS", "小程序", "Node.js",
    # 后端 & 框架
    "Django", "Flask", "FastAPI", "Spring Boot", "Express", "Gin",
    # AI & 数据
    "AI大模型", "机器学习", "深度学习", "NLP", "计算机视觉",
    "数据分析", "数据挖掘", "推荐系统",
    # 数据库
    "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch",
    # 基础设施
    "Docker", "Kubernetes", "Linux", "Nginx", "DevOps", "CI/CD",
    # 网络 & 安全
    "TCP/IP", "HTTP", "网络安全", "密码学",
    # 其他
    "算法", "数据结构", "操作系统", "分布式系统", "微服务",
    "区块链", "嵌入式", "游戏开发", "测试", "其他",
]


# ── 辅助函数 ───

def _get_user_question(question_id: int, user_id: int, db: Session) -> Question:
    question = db.query(Question).filter(Question.id == question_id, Question.user_id == user_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")
    return question


def _apply_tags(question: Question, tag_names: list[str], db: Session):
    tags = []
    for name in tag_names:
        name = name.strip()
        if not name:
            continue
        tag = db.query(Tag).filter(Tag.name == name).first()
        if not tag:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()
        tags.append(tag)
    question.tags = tags


def _question_to_out(q: Question) -> QuestionOut:
    return QuestionOut(
        id=q.id,
        title=q.title,
        content=q.content,
        answer=q.answer,
        tech_stack=q.tech_stack,
        difficulty=q.difficulty,
        mastery=q.mastery,
        source=q.source,
        is_archived=q.is_archived,
        published_post_id=q.published_post_id,
        is_published=bool(q.published_post_id),
        tags=[t.name for t in q.tags],
        created_at=q.created_at,
        updated_at=q.updated_at,
    )
