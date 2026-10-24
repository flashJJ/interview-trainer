"""混合检索：向量召回 + BM25 召回 + RRF 融合 + 查询改写。

为什么需要混合：
- 纯向量（本项目内置的是 n-gram 哈希向量）擅长"意思相近"，但对**精确术语**
  不敏感——查 "volatile 关键字" 时，语义上相邻的"内存可见性"段落可能挤掉真正
  讲 volatile 的那一段；
- 纯 BM25 擅长精确术语，但完全不理解同义改写；
- 两者召回集合重叠度低，融合收益明显（这也是工业界 RAG 的默认做法）。

融合用 RRF（Reciprocal Rank Fusion）而不是分数加权：
两种分数量纲完全不同（余弦 0~1，BM25 无上界），归一化后加权对参数极敏感；
RRF 只看名次，无需调权重，鲁棒性好。

    RRF(d) = Σ_i w_i / (k + rank_i(d))      k 默认 60（原论文取值）
"""

import threading
from dataclasses import dataclass, field

from sqlalchemy import func

from ..models import KnowledgeChunk, KnowledgeEntry
from . import text_utils
from .bm25 import BM25Index
from .runtime import get_embeddings, get_vector_store

RRF_K = 60
CHANNEL_CANDIDATES = 20  # 每个通道先召回 20 条参与融合

# 检索模式
MODE_VECTOR = "vector"
MODE_BM25 = "bm25"
MODE_HYBRID = "hybrid"
MODES = (MODE_VECTOR, MODE_BM25, MODE_HYBRID)


@dataclass
class RetrievalHit:
    chunk_id: int
    entry_id: int | None
    seq: int
    content: str
    score: float
    vector_score: float = 0.0
    bm25_score: float = 0.0
    channels: list[str] = field(default_factory=list)
    vector_rank: int | None = None
    bm25_rank: int | None = None

    def as_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "entry_id": self.entry_id,
            "seq": self.seq,
            "content": self.content,
            "score": round(self.score, 6),
            "vector_score": round(self.vector_score, 4),
            "bm25_score": round(self.bm25_score, 4),
            "channels": list(self.channels),
            "vector_rank": self.vector_rank,
            "bm25_rank": self.bm25_rank,
        }


# ---------------------------------------------------------------- 语料与索引缓存
_index_cache: dict[int, tuple[tuple, BM25Index]] = {}
_cache_lock = threading.Lock()


def _corpus_version(db, user_id: int) -> tuple:
    """语料版本：(块数量, 最大块 id)。

    知识块在本系统里是"随资料处理一次性生成、随资料删除一起消失"的，
    因此这两个值一变就说明语料变了，需要重建索引。
    """
    row = (
        db.query(func.count(KnowledgeChunk.id), func.max(KnowledgeChunk.id))
        .join(KnowledgeEntry, KnowledgeEntry.id == KnowledgeChunk.entry_id)
        .filter(KnowledgeEntry.user_id == user_id)
        .one()
    )
    return (int(row[0] or 0), int(row[1] or 0))


def load_corpus(db, user_id: int) -> list[dict]:
    """加载用户全部知识块（检索与评测共用的语料视图）。"""
    rows = (
        db.query(
            KnowledgeChunk.id,
            KnowledgeChunk.entry_id,
            KnowledgeChunk.seq,
            KnowledgeChunk.content,
        )
        .join(KnowledgeEntry, KnowledgeEntry.id == KnowledgeChunk.entry_id)
        .filter(KnowledgeEntry.user_id == user_id)
        .order_by(KnowledgeChunk.id)
        .all()
    )
    return [
        {"chunk_id": int(r[0]), "entry_id": int(r[1]), "seq": int(r[2]), "content": r[3] or ""}
        for r in rows
    ]


def get_bm25_index(db, user_id: int, corpus: list[dict] | None = None) -> BM25Index:
    version = _corpus_version(db, user_id)
    with _cache_lock:
        cached = _index_cache.get(user_id)
    if cached is not None and cached[0] == version:
        return cached[1]
    docs = corpus if corpus is not None else load_corpus(db, user_id)
    index = BM25Index([(d["chunk_id"], d["content"]) for d in docs])
    with _cache_lock:
        _index_cache[user_id] = (version, index)
    return index


def invalidate_index(user_id: int | None = None) -> None:
    """清空索引缓存（资料增删/改配置后调用；不调用也会因版本变化自动重建）。"""
    with _cache_lock:
        if user_id is None:
            _index_cache.clear()
        else:
            _index_cache.pop(user_id, None)


# ---------------------------------------------------------------- 查询改写
def rewrite_query(query: str, use_llm: bool = False) -> list[str]:
    """把用户问题改写成多条检索式，返回 [原始查询, ...改写] 去重列表。

    规则版（永远可用）：抽关键词串，去掉"是什么/怎么/为什么"这类疑问壳。
    LLM 版（配置了 Key 才启用）：让模型给出 2 条术语密集的检索式。
    """
    variants: list[str] = [query.strip()] if query.strip() else []

    keywords = text_utils.top_terms([query], top_k=6)
    if keywords:
        kw_query = " ".join(keywords)
        if kw_query and kw_query not in variants:
            variants.append(kw_query)

    if use_llm:
        for extra in _llm_rewrite(query):
            if extra and extra not in variants:
                variants.append(extra)

    return variants[:4]


def _llm_rewrite(query: str) -> list[str]:
    """LLM 查询改写（失败静默降级为规则版，不影响检索可用性）。"""
    try:
        from .runtime import get_llm

        llm = get_llm()
        if not llm.enabled:
            return []
        data = llm.chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "你是检索查询改写器。把用户的问题改写成 2 条用于技术文档检索的查询式："
                        "术语密集、去掉口语化疑问词、保留关键实体。"
                        '只输出 JSON：{"queries": ["查询1", "查询2"]}'
                    ),
                },
                {"role": "user", "content": query},
            ],
            temperature=0.2,
        )
        items = data.get("queries") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return []
        return [str(x).strip() for x in items if str(x).strip()][:2]
    except Exception:  # noqa: BLE001 - 改写是增强项，任何失败都退回规则版
        return []


# ---------------------------------------------------------------- 单通道召回
def _entry_ids(db, user_id: int) -> list[int]:
    return [
        int(row[0])
        for row in db.query(KnowledgeEntry.id).filter(KnowledgeEntry.user_id == user_id).all()
    ]


def vector_search(
    db,
    user_id: int,
    query: str,
    top_k: int = CHANNEL_CANDIDATES,
    entry_ids: list[int] | None = None,
    embedding: list[float] | None = None,
) -> list[tuple[int, float]]:
    """向量召回，返回 [(chunk_id, 余弦相似度)]。

    embedding 可外部传入以复用（评测时同一查询要在多个模式下重复使用）。
    """
    ids = entry_ids if entry_ids is not None else _entry_ids(db, user_id)
    if not ids:
        return []
    vec = embedding if embedding is not None else get_embeddings().embed(query)
    hits = get_vector_store().search_chunks(vec, top_k=top_k, entry_ids=ids)
    out: list[tuple[int, float]] = []
    for hit in hits:
        try:
            chunk_id = int(str(hit["vector_id"]).split("_")[-1])
        except (ValueError, IndexError):
            continue
        out.append((chunk_id, float(hit.get("score") or 0.0)))
    return out


def bm25_search(db, user_id: int, query: str, top_k: int = CHANNEL_CANDIDATES) -> list[tuple[int, float]]:
    """BM25 召回，返回 [(chunk_id, bm25 分)]。"""
    index = get_bm25_index(db, user_id)
    return index.search(query, top_k=top_k)


# ---------------------------------------------------------------- 融合
def rrf_fuse(
    ranked_lists: list[list[tuple[int, float]]], k: int = RRF_K, weights: list[float] | None = None
) -> list[tuple[int, float]]:
    """RRF 融合多路有序结果，返回 [(chunk_id, rrf 分)] 降序。"""
    scores: dict[int, float] = {}
    for i, ranked in enumerate(ranked_lists):
        weight = weights[i] if weights and i < len(weights) else 1.0
        for rank, (chunk_id, _raw) in enumerate(ranked, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + weight / (k + rank)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


# ---------------------------------------------------------------- 对外主入口
def retrieve(
    db,
    user_id: int,
    query: str,
    top_k: int = 5,
    mode: str = MODE_HYBRID,
    use_rewrite: bool = False,
    use_llm_rewrite: bool = False,
    embedding_cache: dict[str, list[float]] | None = None,
    vector_weight: float = 1.0,
) -> list[RetrievalHit]:
    """按指定模式检索，返回按融合分降序的命中列表。

    top_k 限制的是**最终返回条数**；每个通道内部固定召回 CHANNEL_CANDIDATES 条
    参与融合，保证被融合进来的候选池足够大。

    embedding_cache：跨模式/跨用例复用的 embedding 字典（评测时传入可显著减少
    对 Embedding API 的调用次数；不传则每次现算）。

    vector_weight：RRF 里向量通道的权重（BM25 恒为 1.0）。内置词法向量较弱时可下调，
    用评测页实测决定取值——这正是"有评测集"的意义。
    """
    if mode not in MODES:
        mode = MODE_HYBRID
    if not (query or "").strip():
        return []

    corpus = load_corpus(db, user_id)
    if not corpus:
        return []
    by_id = {d["chunk_id"]: d for d in corpus}

    variants = rewrite_query(query, use_llm=use_llm_rewrite) if use_rewrite else [query]
    entry_ids = sorted({d["entry_id"] for d in corpus})

    lists: list[list[tuple[int, float]]] = []
    weights: list[float] = []
    kinds: list[str] = []
    for variant in variants:
        if mode in (MODE_VECTOR, MODE_HYBRID):
            vec = _cached_embed(variant, embedding_cache)
            lists.append(vector_search(db, user_id, variant, CHANNEL_CANDIDATES, entry_ids, vec))
            weights.append(vector_weight)
            kinds.append("vector")
        if mode in (MODE_BM25, MODE_HYBRID):
            lists.append(bm25_search(db, user_id, variant, CHANNEL_CANDIDATES))
            weights.append(1.0)
            kinds.append("bm25")

    # 单通道模式下若只有一路结果，直接按原始分排序（保留可读的分数语义）
    fused = rrf_fuse(lists, weights=weights)

    vector_best = _best_by_channel(lists, kinds, "vector")
    bm25_best = _best_by_channel(lists, kinds, "bm25")

    hits: list[RetrievalHit] = []
    for chunk_id, rrf_score in fused[: max(top_k, 0)]:
        doc = by_id.get(chunk_id)
        if doc is None:
            continue  # 向量库残留但关系库里已删，跳过
        v_rank, v_score = vector_best.get(chunk_id, (None, 0.0))
        b_rank, b_score = bm25_best.get(chunk_id, (None, 0.0))
        channels = [name for name, r in (("vector", v_rank), ("bm25", b_rank)) if r]
        hits.append(
            RetrievalHit(
                chunk_id=chunk_id,
                entry_id=doc["entry_id"],
                seq=doc["seq"],
                content=doc["content"],
                score=rrf_score,
                vector_score=v_score,
                bm25_score=b_score,
                channels=channels,
                vector_rank=v_rank,
                bm25_rank=b_rank,
            )
        )
    return hits


def _best_by_channel(
    lists: list[list[tuple[int, float]]], kinds: list[str], channel: str
) -> dict[int, tuple[int, float]]:
    """每个 chunk 在该通道所有查询式里的最好名次与原始分（名次优先，同分取高分）。"""
    best: dict[int, tuple[int, float]] = {}
    for ranked, kind in zip(lists, kinds):
        if kind != channel:
            continue
        for rank, (chunk_id, raw) in enumerate(ranked, start=1):
            prev = best.get(chunk_id)
            if prev is None or rank < prev[0] or (rank == prev[0] and raw > prev[1]):
                best[chunk_id] = (rank, raw)
    return best


# ---------------------------------------------------------------- 评测指标
def recall_at_k(ranked_ids: list[int], expected: list[int], k: int = 5) -> float:
    """Recall@k = 命中期望块数 / 期望块总数（期望为空时记 0，避免虚高）。"""
    if not expected:
        return 0.0
    top = set(ranked_ids[:k])
    return len(top & set(expected)) / len(set(expected))


def reciprocal_rank(ranked_ids: list[int], expected: list[int], k: int = 10) -> float:
    """RR 的 1/首个命中名次（用于 MRR@k）。"""
    expected_set = set(expected)
    for rank, chunk_id in enumerate(ranked_ids[:k], start=1):
        if chunk_id in expected_set:
            return 1.0 / rank
    return 0.0


def hit_at_1(ranked_ids: list[int], expected: list[int]) -> float:
    return 1.0 if ranked_ids and ranked_ids[0] in set(expected) else 0.0


def _cached_embed(text: str, cache: dict[str, list[float]] | None) -> list[float] | None:
    """返回缓存的 embedding；cache 为 None 时返回 None 让调用方现算。"""
    if cache is None:
        return None
    if text not in cache:
        cache[text] = get_embeddings().embed(text)
    return cache[text]


def retrieve_ids(
    db,
    user_id: int,
    query: str,
    top_k: int = 5,
    mode: str = MODE_HYBRID,
    **kwargs,
) -> list[int]:
    """只要 id 列表的便捷封装（评测与内部调用用）。"""
    return [h.chunk_id for h in retrieve(db, user_id, query, top_k=top_k, mode=mode, **kwargs)]
