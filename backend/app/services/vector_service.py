"""向量检索服务: FAISS + Ollama embedding 模型 (qwen3-embedding:0.6b)"""
import os
import json
import time
import logging

import numpy as np

from ..config import settings

logger = logging.getLogger(__name__)

DATA_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
INDEX_PATH = os.path.join(DATA_DIR, "faiss.index")
META_PATH = os.path.join(DATA_DIR, "faiss_meta.json")


def _write_index_file(index, path: str):
    """写索引到文件

    faiss 的 C++ FileIOWriter 用 fopen 打开路径，在 Windows 上不支持中文目录，
    会报 "could not open ... No such file or directory"。
    这里改为序列化到内存、再由 Python 写文件（Python 的文件 IO 原生支持 Unicode 路径）。
    """
    import faiss
    with open(path, "wb") as f:
        faiss.write_index(index, faiss.PyCallbackIOWriter(f.write))


def _read_index_file(path: str):
    """从文件读索引（同上，绕开 faiss 的 fopen 以支持中文路径）"""
    import faiss
    with open(path, "rb") as f:
        return faiss.read_index(faiss.PyCallbackIOReader(f.read))

_index = None
_meta: dict = {}
_ollama_ok: bool = False       # 探测成功后长期缓存
_last_probe_fail: float = 0.0  # 上次探测失败时间，用于限流重试
_PROBE_RETRY_INTERVAL = 30     # 秒：ollama 不可用时，30 秒内不再重复探测


def _check_ollama() -> bool:
    """检查 ollama 服务是否可用（失败结果只缓存 30 秒，便于服务重启后自动恢复）"""
    global _ollama_ok, _last_probe_fail
    if _ollama_ok:
        return True

    now = time.time()
    if now - _last_probe_fail < _PROBE_RETRY_INTERVAL:
        return False

    try:
        import httpx
        resp = httpx.get(f"{settings.ollama_host}/api/version", timeout=3)
        if resp.status_code == 200:
            _ollama_ok = True
            logger.info(f"Ollama 可用: {resp.json().get('version', 'unknown')}")
            return True
    except Exception as e:
        logger.warning(f"Ollama 不可用: {e}")

    _last_probe_fail = now
    return False


def _get_embedding(text: str) -> list[float] | None:
    """通过 Ollama /api/embed 获取文本向量"""
    if not _check_ollama():
        return None
    try:
        import httpx
        resp = httpx.post(
            f"{settings.ollama_host}/api/embed",
            json={"model": settings.ollama_embed_model, "input": text},
            timeout=60,
        )
        if resp.status_code == 200:
            data = resp.json()
            # ollama 返回格式: {"embeddings": [[...]]}
            if data.get("embeddings"):
                return data["embeddings"][0]
        else:
            logger.warning(
                f"Ollama embedding 返回 {resp.status_code}（模型 {settings.ollama_embed_model}）: {resp.text[:200]}"
            )
    except Exception as e:
        logger.warning(f"Ollama embedding 失败: {e}")
    return None


def _load_index():
    global _index, _meta
    if _index is not None:
        return
    if os.path.exists(INDEX_PATH) and os.path.exists(META_PATH):
        try:
            _index = _read_index_file(INDEX_PATH)
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
    _index = faiss.IndexFlatIP(dim)  # 内积相似度（向量已归一化 = 余弦相似度）
    _meta = {}


def _save_index():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        _write_index_file(_index, INDEX_PATH)
        with open(META_PATH, "w", encoding="utf-8") as f:
            json.dump(_meta, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"向量索引保存失败 (内存中仍可用): {e}")


def add_question(question_id: int, text: str) -> bool:
    """将题目文本向量化并加入索引，成功返回 True"""
    embedding = _get_embedding(text)
    if embedding is None:
        return False
    _load_index()
    if _index is None:
        return False

    import faiss
    vec = np.array([embedding], dtype="float32")
    faiss.normalize_L2(vec)
    _index.add(vec)
    _meta[str(_index.ntotal - 1)] = {"question_id": question_id, "text": text[:200]}
    _save_index()
    return True


def indexed_ids() -> set:
    """已存在于向量索引中的题目 ID 集合"""
    _load_index()
    return {info["question_id"] for info in _meta.values()}


def is_available() -> bool:
    """embedding 能力是否可用（ollama 在线且模型能返回向量）"""
    return _get_embedding("ping") is not None


def remove_question(question_id: int):
    """从索引中移除题目 (重建索引)"""
    # _meta 在下方 else 分支有赋值，必须声明 global，否则会被当成局部变量
    global _index, _meta
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

    import faiss
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
