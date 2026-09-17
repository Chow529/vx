"""文件解析工具：从 PDF / Word / Markdown 提取 QA 对"""
import re
import logging
from typing import List

from ..schemas.question import ParsedQA

logger = logging.getLogger(__name__)


def parse_file(filename: str, content: bytes) -> List[ParsedQA]:
    """根据文件扩展名选择解析器"""
    ext = filename.rsplit(".", 1)[-1].lower()
    
    if ext == "pdf":
        items = _parse_pdf(content)
    elif ext in ("doc", "docx"):
        items = _parse_docx(content)
    elif ext == "md":
        items = _parse_markdown(content.decode("utf-8", errors="replace"))
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
        text += page.extract_text() or ""
    return _extract_qa_pairs(text)


def _parse_docx(content: bytes) -> List[ParsedQA]:
    from docx import Document
    import io

    doc = Document(io.BytesIO(content))
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return _extract_qa_pairs(text)


def _parse_markdown(text: str) -> List[ParsedQA]:
    # 移除 Markdown 标题标记但保留文本
    cleaned = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    return _extract_qa_pairs(cleaned)


def _extract_qa_pairs(text: str) -> List[ParsedQA]:
    """
    启发式解析 QA 对。
    策略:
    1. 先尝试按 "Q:" / "A:" 或 "问:" / "答:" 分隔符切分
    2. 若无明确分隔符，将以 ? 结尾的行视为问题，后续段落视为答案
    3. 最后兜底：按空行分段，奇数段为问题，偶数段为答案
    """
    text = text.strip()
    if not text:
        return []

    # 策略 1: Q:/A: 格式
    qa_pattern = re.findall(
        r"(?:Q|问)[：:]\s*(.+?)(?:\n(?:A|答)[：:]\s*(.+?))?(?=\n(?:Q|问)[：:]|\Z)",
        text, re.DOTALL
    )
    if qa_pattern:
        return [ParsedQA(question=q.strip(), answer=a.strip()) for q, a in qa_pattern]

    # 策略 2: 以问号结尾的行作为问题
    blocks = re.split(r"\n\s*\n", text)
    pairs = []
    i = 0
    while i < len(blocks):
        block = blocks[i].strip()
        if not block:
            i += 1
            continue
        # 如果这个 block 以问号结尾，视为问题
        if block.rstrip().endswith(("?", "？")):
            answer = blocks[i + 1].strip() if i + 1 < len(blocks) else ""
            # 不要把下一个问号开头的 block 当答案
            if answer and answer.rstrip().endswith(("?", "？")) and len(answer) < 80:
                pairs.append(ParsedQA(question=block, answer=""))
                i += 1
            else:
                pairs.append(ParsedQA(question=block, answer=answer))
                i += 2
            continue
        # 否则整段作为问题 (无答案)
        pairs.append(ParsedQA(question=block, answer=""))
        i += 1

    return pairs if pairs else [ParsedQA(question=text[:256], answer="")]
