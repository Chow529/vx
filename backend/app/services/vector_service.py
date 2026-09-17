"""向量检索服务: FAISS + Ollama (qwen3.5:2b)"""
import os
import json
import logging

import numpy as np

from ..config import settings

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
INDEX_PATH = os.path.join(DATA_DIR, "faiss.index")
META_PATH = os.path.join(DATA_DIR, "faiss_meta.json")

# Ollama 配置
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen3.5:2b"

_index = None
_meta: dict = {}
_model_available: bool | None = None


def _check_ollama():
    """检查 ollama 是否可用"""
    global _model_available
    if _model_available is not None:
        return _model_available
    try:
        import httpx
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/version", timeout=3)
        if resp.status_code == 200:
            _model_available = True
            logger.info(f"Ollama 可用: {resp.json().get('version', 'unknown')}")
            return True
    except Exception as e:
        logger.warning(f"Ollama 不可用: {e}")
    _model_available = False
    return False


def _get_embedding(text: str) -> list[float] | None:
    """通过 Ollama API 获取文本向量"""
    if not _check_ollama():
        return None
    try:
        import httpx
        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/embed",
            json={"model": OLLAMA_MODEL, "input": text},
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            # ollama 返回格式: {"embeddings": [[...]]}
            if "embeddings" in data and len(data["embeddings"]) > 0:
                return data["embeddings"][0]
    except Exception as e:
        logger.warning(f"Ollama embedding 失败: {e}")
    return None


def _load_index():
    global _index, _meta
    if _index is not None:
        return
    if os.path.exists(INDEX_PATH) and os.path.exists(META_PATH):
        try:
            import faiss
            _index = faiss.read_index(INDEX_PATH)
            with open(META_PATH, "r", encoding="utf-8") as f:
                _meta = json.load(f)
            return
        except Exception as e:
            logger.warning(f"向量索引加载失败: {e}")
    
    # 获取一个示例向量确定维度
    sample = _get_embedding("test")
    if sample is None:
        _index = None
        _meta = {}
        return
    
    import faiss
    dim = len(sample)
    _index = faiss.IndexFlatIP(dim)  # 内积相似度
    # 归一化
    faiss.normalize_L2(_index)
    _meta = {}


def _save_index():
    import faiss
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        faiss.write_index(_index, INDEX_PATH)
        with open(META_PATH, "w", encoding="utf-8") as f:
            json.dump(_meta, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"向量索引保存失败 (内存中仍可用): {e}")


def add_question(question_id: int, text: str):
    """将题目文本向量化并加入索引"""
    embedding = _get_embedding(text)
    if embedding is None:
        return
    _load_index()
    if _index is None:
        return
    
    vec = np.array([embedding], dtype="float32")
    faiss.normalize_L2(vec)
    _index.add(vec)
    _meta[str(_index.ntotal - 1)] = {"question_id": question_id, "text": text[:200]}
    _save_index()


def remove_question(question_id: int):
    """从索引中移除题目 (重建索引)"""
    global _index
    _load_index()
    if _index is None:
        return
    
    keep_ids = []
    for idx_str, info in _meta.items():
        if info["question_id"] != question_id:
            keep_ids.append(int(idx_str))

    if len(keep_ids) == _index.ntotal:
        return

    import faiss
    
    if keep_ids:
        vectors = []
        new_meta = {}
        for old_idx in sorted(keep_ids):
            vec = _index.reconstruct(old_idx)
            vectors.append(vec)
            new_meta[str(len(vectors) - 1)] = _meta[str(old_idx)]

        vectors = np.array(vectors, dtype="float32")
        _index = faiss.IndexFlatIP(vectors.shape[1])
        faiss.normalize_L2(vectors)
        _index.add(vectors)
        _meta.clear()
        _meta.update(new_meta)
    else:
        sample = _get_embedding("test")
        if sample:
            _index = faiss.IndexFlatIP(len(sample))
        else:
            _index = None
        _meta = {}
    
    _save_index()


def search_similar(text: str, top_k: int = 10) -> list:
    """语义搜索, 返回 [(question_id, score), ...]"""
    embedding = _get_embedding(text)
    if embedding is None:
        return []
    _load_index()
    if _index is None or _index.ntotal == 0:
        return []

    vec = np.array([embedding], dtype="float32")
    faiss.normalize_L2(vec)
    scores, indices = _index.search(vec, min(top_k, _index.ntotal))

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue
        key = str(idx)
        if key in _meta:
            results.append({
                "question_id": _meta[key]["question_id"],
                "score": float(score),
            })
    return results


def rebuild_index(questions: list):
    """全量重建索引, questions = [(question_id, text), ...]"""
    global _index, _meta
    import faiss
    _load_index()
    
    if not questions:
        _save_index()
        return
    
    embeddings = []
    for qid, text in questions:
        emb = _get_embedding(text)
        if emb:
            embeddings.append((qid, emb, text))
    
    if not embeddings:
        return
    
    vectors = np.array([e[1] for e in embeddings], dtype="float32")
    faiss.normalize_L2(vectors)
    _index = faiss.IndexFlatIP(vectors.shape[1])
    _index.add(vectors)
    _meta = {}
    
    for i, (qid, _, text) in enumerate(embeddings):
        _meta[str(i)] = {"question_id": qid, "text": text[:200]}
    
    _save_index()
