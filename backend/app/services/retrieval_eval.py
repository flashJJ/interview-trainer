"""检索评测：评测集自动生成 + 多模式指标计算。

评测口径（写进文档与报告页，避免"看起来变好了"）：
- Recall@k = 命中期望块数 / 该用例期望块总数，再对全部用例取平均
- MRR@10    = 首个命中名次倒数的平均
- Hit@1     = 首位即命中的比例

**已知局限**：自动生成的查询来自知识块本身（关键词或主题句），存在词面泄漏，
指标绝对值偏乐观。因此报告以**同口径下的相对提升**为主要结论，绝对值只做参考；
需要严格口径时用「手工录入」用例（真实提问 → 人工标注期望块）。
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor

from ..models import KnowledgeChunk, KnowledgeEntry, RetrievalEvalCase
from . import retrieval, text_utils

# 报告页固定跑这几档，用于对比"每一步技术各自带来多少增益"
MODES_FOR_REPORT = [
    ("vector", retrieval.MODE_VECTOR, False),
    ("bm25", retrieval.MODE_BM25, False),
    ("hybrid", retrieval.MODE_HYBRID, False),
    ("hybrid+rewrite", retrieval.MODE_HYBRID, True),
]

# 太短的块信息量不足，反推出来的查询也没什么区分度
MIN_CHUNK_CHARS = 40


# ---------------------------------------------------------------- 用例生成
def build_query_from_chunk(content: str, use_llm: bool = False, term_count: int = 3) -> str:
    """从知识块反推一个检索查询。

    优先用 LLM 生成自然提问（更贴近真实使用）；无 LLM 时抽关键词拼成
    "术语 术语 是什么" 的形式，刻意不复制原句，尽量减少词面泄漏。

    term_count 用于同一主题多个块时扩词去重（见 auto_build_cases）。
    """
    if use_llm:
        query = _llm_query(content)
        if query:
            return query
    terms = text_utils.top_terms([content], top_k=max(term_count, 6))
    if len(terms) >= 2:
        return " ".join(terms[:term_count]) + " 是什么"
    sentences = [s.strip() for s in text_utils.split_sentences(content) if len(s.strip()) >= 12]
    if sentences:
        return sentences[0][:80]
    return content.strip()[:60]


def _llm_query(content: str) -> str:
    """让 LLM 写一个技术面试者会问的问题（失败则返回空串，回落规则版）。

    注意：这里必须用 llm.chat_json()，不是模块级的 extract_json()——
    后者只做「字符串 → JSON」解析，不负责发请求。
    """
    try:
        from .runtime import get_llm

        llm = get_llm()
        if not llm.enabled:
            return ""
        data = llm.chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "根据下面这段技术资料，写一个技术面试者可能提出的检索式问题。"
                        "要求：一句话、不超过 30 字、必须换一种说法（不要直接照抄原文里的"
                        "连续词组，尽量用近义表达或从原理角度提问）、不要出现「这段资料」等字眼。"
                        '只输出 JSON：{"query": "..."}'
                    ),
                },
                {"role": "user", "content": content[:800]},
            ],
            temperature=0.5,
        )
        query = (data or {}).get("query") if isinstance(data, dict) else ""
        return str(query).strip()[:120]
    except Exception:  # noqa: BLE001 - 生成失败即降级
        return ""


def auto_build_cases(db, user_id: int, count: int, use_llm: bool = False) -> tuple[int, int, int]:
    """自动生成评测集，返回 (新建数, 跳过数, 当前总用例数)。

    抽样策略：按资料轮转取块（避免全落在同一篇资料里），优先长块（信息更完整），
    跳过过短块与已用过的块。
    """
    rows = (
        db.query(KnowledgeChunk.id, KnowledgeChunk.entry_id, KnowledgeChunk.content)
        .join(KnowledgeEntry, KnowledgeEntry.id == KnowledgeChunk.entry_id)
        .filter(KnowledgeEntry.user_id == user_id)
        .order_by(KnowledgeChunk.entry_id, KnowledgeChunk.seq)
        .all()
    )
    if not rows:
        return (0, 0, 0)

    used_chunk_ids = {
        int(r[0])
        for r in db.query(RetrievalEvalCase.origin_chunk_id)
        .filter(RetrievalEvalCase.user_id == user_id)
        .all()
    }
    used_queries = {
        (r[0] or "").strip()
        for r in db.query(RetrievalEvalCase.query).filter(RetrievalEvalCase.user_id == user_id).all()
    }

    # 按资料分组轮转
    buckets: dict[int, list[tuple[int, str]]] = {}
    for chunk_id, entry_id, content in rows:
        if chunk_id in used_chunk_ids or len((content or "").strip()) < MIN_CHUNK_CHARS:
            continue
        buckets.setdefault(int(entry_id), []).append((int(chunk_id), content or ""))
    for bucket in buckets.values():
        bucket.sort(key=lambda item: len(item[1]), reverse=True)

    picked: list[tuple[int, str]] = []
    while len(picked) < count and any(buckets.values()):
        for entry_id in list(buckets.keys()):
            if len(picked) >= count:
                break
            bucket = buckets[entry_id]
            if bucket:
                picked.append(bucket.pop(0))

    created = 0
    skipped = 0

    # LLM 逐块生成查询是网络调用（实测 16~40s/条），必须并发；写入仍在主线程串行
    queries: list[tuple[int, str, str]] = []
    if use_llm and picked:
        with ThreadPoolExecutor(max_workers=min(len(picked), 6)) as pool:
            futures = [
                pool.submit(build_query_from_chunk, content, True)
                for _chunk_id, content in picked
            ]
            generated = [f.result() for f in futures]
        pairs = [(picked[i][0], picked[i][1], generated[i]) for i in range(len(picked))]
    else:
        pairs = [
            (chunk_id, content, build_query_from_chunk(content, use_llm=False))
            for chunk_id, content in picked
        ]

    for chunk_id, content, query in pairs:
        # 同一主题的多个块容易生成同名查询：逐步扩词直到不与已有用例撞车
        if query in used_queries:
            for n in (4, 5, 6):
                alt = build_query_from_chunk(content, use_llm=False, term_count=n)
                if alt and alt not in used_queries and alt != query:
                    query = alt
                    break
        if not query or len(query) < 4 or query in used_queries:
            skipped += 1
            continue
        db.add(
            RetrievalEvalCase(
                user_id=user_id,
                query=query,
                expected_ids_json=json.dumps([chunk_id]),
                source="auto",
                origin_chunk_id=chunk_id,
                note="自动生成",
            )
        )
        used_queries.add(query)
        created += 1
    db.commit()
    total = db.query(RetrievalEvalCase).filter(RetrievalEvalCase.user_id == user_id).count()
    return (created, skipped, int(total))


# ---------------------------------------------------------------- 评测运行
def run_evaluation(
    db,
    user_id: int,
    cases: list[RetrievalEvalCase],
    top_k: int = 5,
    use_rewrite: bool = False,
    include_llm_rewrite: bool = False,
    vector_weight: float = 1.0,
) -> tuple[dict, list, int]:
    """对给定用例跑全部模式，返回 (summary, detail, elapsed_ms)。

    use_rewrite 控制是否把「hybrid+rewrite」那一档也算进去；
    为公平起见，三档基线（vector/bm25/hybrid）永远不开改写。
    vector_weight 只影响 hybrid 两档（vector/bm25 是单通道，权重无意义）。
    """
    started = time.perf_counter()
    cache: dict[str, list[float]] = {}

    modes = [(name, mode, False) for name, mode, _ in MODES_FOR_REPORT[:3]]
    if use_rewrite:
        modes.append(("hybrid+rewrite", retrieval.MODE_HYBRID, True))

    detail: list[dict] = []
    totals: dict[str, dict[str, float]] = {name: {"recall": 0.0, "mrr": 0.0, "hit1": 0.0} for name, _, _ in modes}

    for case in cases:
        expected = case.expected_ids
        per_mode: dict[str, dict] = {}
        for name, mode, rewrite in modes:
            ranked = retrieval.retrieve_ids(
                db,
                user_id,
                case.query,
                top_k=top_k,
                mode=mode,
                use_rewrite=rewrite,
                use_llm_rewrite=include_llm_rewrite and rewrite,
                embedding_cache=cache,
                vector_weight=vector_weight,
            )
            rec = retrieval.recall_at_k(ranked, expected, k=top_k)
            mrr = retrieval.reciprocal_rank(ranked, expected, k=10)
            hit1 = retrieval.hit_at_1(ranked, expected)
            per_mode[name] = {"ranked": ranked, "recall": rec, "mrr": mrr, "hit1": hit1}
            totals[name]["recall"] += rec
            totals[name]["mrr"] += mrr
            totals[name]["hit1"] += hit1
        detail.append(
            {
                "case_id": case.id,
                "query": case.query,
                "expected": expected,
                "modes": per_mode,
            }
        )

    n = max(len(cases), 1)
    summary = {
        name: {
            "recall": round(vals["recall"] / n, 4),
            "mrr": round(vals["mrr"] / n, 4),
            "hit_at_1": round(vals["hit1"] / n, 4),
        }
        for name, vals in totals.items()
    }
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return summary, detail, elapsed_ms
