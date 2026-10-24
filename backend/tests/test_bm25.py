"""BM25 索引单测：打分单调性、边界情况、停用词与长度归一化。"""

from app.services.bm25 import BM25Index
from app.services.text_utils import is_noise_token, tokenize


DOCS = [
    (1, "GIL 是全局解释器锁，保证同一时刻只有一个线程执行字节码。"),
    (2, "多进程通过 multiprocessing 创建独立进程，每个进程有独立的 GIL。"),
    (3, "asyncio 使用事件循环实现单线程并发，适合 IO 密集场景。"),
]


def test_search_returns_ranked_hits():
    index = BM25Index(DOCS)
    hits = index.search("GIL 全局解释器锁", top_k=3)
    assert hits, "应至少召回一条"
    assert hits[0][0] in (1, 2)
    # 分数必须单调不增
    scores = [s for _, s in hits]
    assert scores == sorted(scores, reverse=True)


def test_unrelated_query_scores_low_or_empty():
    index = BM25Index(DOCS)
    hits = index.search("红烧肉的做法", top_k=3)
    # 中文 2-gram 可能偶然命中"做法"之类，但不应排到第一位且分数应很低
    if hits:
        assert hits[0][1] < 1.0


def test_empty_index_and_query():
    assert BM25Index([]).search("GIL") == []
    index = BM25Index(DOCS)
    assert index.search("") == []
    assert index.search("的 了 是") == []  # 全是停用词


def test_rare_term_outranks_common_term():
    """idf 起作用：只在 1 篇出现的 n-gram，权重应高于 3 篇都出现的 n-gram。"""
    common = "缓存"
    docs = [
        (1, f"{common} 缓存穿透 缓存击穿 布隆过滤器"),
        (2, f"{common} 缓存雪崩 过期时间 随机化"),
        (3, f"{common} 本地缓存 分布式缓存 一致性"),
    ]
    index = BM25Index(docs)
    # term 是字符 n-gram，不是整词：这里用实际存在的 gram 比较
    assert "布隆" in index._postings and "缓存" in index._postings
    assert index._idf("布隆") > index._idf(common)


def test_length_normalization_prefers_focused_doc():
    """同样命中一次，短文档（更聚焦）应比长文档得分高。"""
    focused = "布隆过滤器可以拦截不存在的键"
    verbose = "布隆过滤器可以拦截不存在的键。" + "缓存相关的其他内容。" * 40
    index = BM25Index([(1, verbose), (2, focused)])
    hits = index.search("布隆过滤器", top_k=2)
    assert hits[0][0] == 2


def test_tokenize_noise_filter_applied():
    """索引里不应包含纯数字或停用词等高噪声 term。"""
    index = BM25Index([(1, "2024 年的 缓存 一致性 是 什么")])
    assert "2024" not in index._postings
    for term in index._postings:
        assert not is_noise_token(term)


def test_index_len_and_vocab():
    index = BM25Index(DOCS)
    assert len(index) == 3
    assert index.vocab_size > 0
    # 空文档会被跳过，不进入索引
    index2 = BM25Index([(1, ""), (2, "有效内容在这里")])
    assert len(index2) == 1
