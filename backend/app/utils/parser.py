"""文件解析工具：从 PDF / Word / Markdown 提取 QA 对

Markdown 标准问答格式（章节感知）：
    ## 第一部分：Agent 基础概念          ← 章节，归属到该章节下所有题目

    ### Q1：什么是 Agent？              ← 问题（Q 后可带序号，冒号中英文均可）

    **A：** LLM 是无状态的文本生成服务…  ← 答案（A 可带 ** 粗体标记）

    ---                                ← 分隔线，忽略

非标准格式的内容不会丢弃：章节/文档标题作为元数据保留，
其余普通段落走启发式兜底解析，仍然产出题目（可在预览时取消勾选）。
"""
import re
import logging
from typing import List, Tuple

from ..schemas.question import ParsedQA

logger = logging.getLogger(__name__)

# 问题标记：Q1：/ Q：/ 问：/ **Q1:**
_Q_MARK = r"(?:\*\*|__)?[ \t]*(?:Q|问)[ \t]*\d*[ \t]*(?:\*\*|__)?[：:][ \t]*"
# 答案标记：A：/ 答：/ **A：**
_A_MARK = r"(?:\*\*|__)?[ \t]*(?:A|答)[ \t]*\d*[ \t]*(?:\*\*|__)?[：:][ \t]*"

_Q_HEAD = re.compile(rf"^{_Q_MARK}(.+)$", re.S)
_A_HEAD = re.compile(rf"^{_A_MARK}(.+)$", re.S)
_A_INLINE = re.compile(rf"(?:^|\n)[ \t]*{_A_MARK}")
_Q_INLINE = re.compile(rf"(?:^|\n)[ \t]*{_Q_MARK}")

# 噪音行：Markdown 分隔线 / 纯符号行
_NOISE_LINE = re.compile(r"^[ \t]*(?:-{3,}|\*{3,}|_{3,}|={3,})[ \t]*$")
# Markdown 标题行
_HEAD_LINE = re.compile(r"^(#{1,6})[ \t]+(.*)$")
# Markdown 引用行（文档说明/前言，不作为题目）
_QUOTE_LINE = re.compile(r"^>[ \t]?")


def parse_file(filename: str, content: bytes) -> List[ParsedQA]:
    """根据文件扩展名选择解析器"""
    ext = filename.rsplit(".", 1)[-1].lower()

    if ext == "pdf":
        items = _parse_pdf(content)
    elif ext in ("doc", "docx"):
        items = _parse_docx(content)
    elif ext in ("md", "markdown"):
        items = _parse_markdown(content.decode("utf-8", errors="replace"))
    elif ext == "txt":
        items = _extract_qa_pairs(content.decode("utf-8", errors="replace"))
    else:
        raise ValueError(f"不支持的文件格式：{ext}")

    logger.info(f"解析文件 {filename}，提取 {len(items)} 道题目")
    return items


def _parse_pdf(content: bytes) -> List[ParsedQA]:
    from PyPDF2 import PdfReader
    import io

    reader = PdfReader(io.BytesIO(content))
    text = ""
    for page in reader.pages:
        text += (page.extract_text() or "") + "\n"
    return _extract_qa_pairs(text)


def _parse_docx(content: bytes) -> List[ParsedQA]:
    from docx import Document
    import io

    doc = Document(io.BytesIO(content))
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return _extract_qa_pairs(text)


# ─── Markdown 结构化解析 ───

def _parse_markdown(text: str) -> List[ParsedQA]:
    """按标准格式解析 Markdown，保留章节归属

    - 任意层级的标题（# / ## / ### …），只要以 Q 开头就视为问题，
      紧随其后的内容作为答案
    - 文档中若存在标准问答，则零散说明文字（前言、引用块、附注）
      不再生成题目，只记录日志，避免混入垃圾条目
    - 文档中若完全没有标准问答，则零散文本走启发式兜底解析，保证内容不丢
    """
    items: List[ParsedQA] = []
    section = ""        # 当前章节名
    cur_q = None        # 已识别、等待答案的问题
    answer_buf: List[str] = []
    loose: List[str] = []    # 未归属任何问题的普通文本
    notes: List[str] = []    # 引用块等文档说明（不作为题目）
    has_standard = False     # 是否识别到标准问答格式

    def flush_question():
        nonlocal cur_q, answer_buf
        if cur_q is not None:
            items.append(ParsedQA(
                question=cur_q,
                answer=_extract_answer("\n".join(answer_buf)),
                section=section,
            ))
        cur_q = None
        answer_buf = []

    def flush_loose():
        """处理未归属的普通文本"""
        nonlocal loose
        block = "\n".join(loose).strip()
        loose = []
        if not block:
            return
        if has_standard:
            # 文档已是标准问答格式：这些是说明性文字，不当作题目
            notes.append(block)
            return
        # 无标准格式时兜底解析，避免内容被丢弃
        for qa in _extract_qa_pairs(block):
            q = (qa.question or "").strip()
            if q:
                items.append(ParsedQA(question=q, answer=qa.answer, section=section))

    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            # 空行是段落边界：答案区内保留原样，普通文本区用作兜底解析的分段依据
            if cur_q is not None:
                answer_buf.append("")
            elif loose and loose[-1] != "":
                loose.append("")
            continue
        if _NOISE_LINE.match(s):
            continue

        head = _HEAD_LINE.match(s)
        if head:
            level = len(head.group(1))
            title = _clean_inline(head.group(2)).strip()
            qm = _Q_HEAD.match(title)
            if qm:
                # 任意层级的标题，只要以 Q 开头就视为问题（不区分 # / ## / ###）
                flush_question()
                flush_loose()
                has_standard = True
                cur_q = qm.group(1).strip()
                continue

            # 普通标题：浅层 → 作为章节元数据；深层 → 保留为内容
            flush_question()
            flush_loose()
            if level <= 2:
                section = title
            elif title:
                loose.append(title)
            continue

        if cur_q is not None:
            answer_buf.append(s)
        elif _QUOTE_LINE.match(s):
            # 引用块（> 开头）是文档说明，不进入题目
            notes.append(_clean_inline(s))
        else:
            loose.append(_clean_inline(s))

    flush_question()
    flush_loose()

    if notes:
        logger.info(f"已跳过 {len(notes)} 段非问答内容（文档说明/前言）："
                    + " | ".join(n[:40] for n in notes))
    return items


def _extract_answer(block: str) -> str:
    """从问题标题之后的内容中提取答案；无 A 标记时整块作为答案（不丢弃）"""
    block = block.strip()
    if not block:
        return ""

    m = _A_HEAD.match(block)
    if m:
        return _clean_inline(m.group(1)).strip()

    # A 标记出现在中间：标记后的全部内容都算答案
    m2 = _A_INLINE.search(block)
    if m2:
        return _clean_inline(block[m2.end():]).strip()

    return _clean_inline(block).strip()


# ─── 纯文本启发式解析（PDF / Word / 兜底）───

def _extract_qa_pairs(text: str) -> List[ParsedQA]:
    """
    启发式解析 QA 对。
    策略:
    1. 按 Q:/Q1:/问: 标记切分，块内再按 A:/答: 拆分问题与答案
    2. 无标记时，以问号结尾的段落视为问题，后续段落视为答案
    3. 最后兜底：整段作为一道无答案的题目（不丢弃内容）
    """
    text = _drop_noise_lines(text).strip()
    if not text:
        return []

    # 策略 1: Q / A 标记
    heads = list(_Q_INLINE.finditer(text))
    if heads:
        pairs = []
        for idx, m in enumerate(heads):
            end = heads[idx + 1].start() if idx + 1 < len(heads) else len(text)
            question, answer = _split_qa_body(text[m.end():end])
            if question:
                pairs.append(ParsedQA(
                    question=_clean_inline(question),
                    answer=_clean_inline(answer),
                ))
        if pairs:
            return pairs

    # 策略 2: 以问号结尾的段落作为问题
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    pairs = []
    i = 0
    while i < len(blocks):
        block = _clean_inline(blocks[i]).strip()
        if not block:
            i += 1
            continue
        if block.rstrip().endswith(("?", "？")):
            answer = _clean_inline(blocks[i + 1]).strip() if i + 1 < len(blocks) else ""
            # 下一段也是短问句时，不当作答案
            if answer and answer.rstrip().endswith(("?", "？")) and len(answer) < 80:
                pairs.append(ParsedQA(question=block, answer=""))
                i += 1
            else:
                pairs.append(ParsedQA(question=block, answer=answer))
                i += 2
            continue
        pairs.append(ParsedQA(question=block, answer=""))
        i += 1

    # 策略 3: 兜底，保证内容不丢
    return pairs if pairs else [ParsedQA(question=_clean_inline(text)[:256], answer="")]


def _split_qa_body(body: str) -> Tuple[str, str]:
    """把 Q 标记之后的一段文本拆成 (问题, 答案)"""
    body = body.strip()
    m = _A_INLINE.search(body)
    if not m:
        return body, ""
    return body[:m.start()].strip(), body[m.end():].strip()


def _drop_noise_lines(text: str) -> str:
    """去掉分隔线等噪音行"""
    kept = [ln for ln in text.splitlines() if not _NOISE_LINE.match(ln.strip())]
    return "\n".join(kept)


def _clean_inline(s: str) -> str:
    """清理 Markdown 内联标记，保留纯文本内容"""
    if not s:
        return ""
    s = re.sub(r"^[ \t]*>[ \t]?", "", s)      # 行首引用符
    s = s.replace("**", "").replace("__", "")  # 粗体
    s = s.replace("`", "")                     # 行内代码
    return s.strip()
