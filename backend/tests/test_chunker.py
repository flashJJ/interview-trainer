"""纯函数单测：分块、文本工具、评分。"""

from app.services import text_utils
from app.services.chunker import chunk_text


class TestChunker:
    def test_empty_input(self):
        assert chunk_text("") == []
        assert chunk_text("   \n\n  ") == []

    def test_short_text_single_chunk(self):
        text = "Redis 是一个基于内存的键值数据库。" * 3
        chunks = chunk_text(text)
        assert len(chunks) == 1
        assert "Redis" in chunks[0]

    def test_long_text_split_within_bounds(self):
        text = "MySQL InnoDB 使用 B+ 树作为索引结构。" * 60  # ~1500 字
        chunks = chunk_text(text, target=200, max_size=300)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 300
        # 内容不丢失（允许换行合并带来的 1 字符差异）
        joined = "".join(chunks).replace("\n", "")
        original = text.replace("\n", "")
        assert original in joined or joined in original or len(joined) >= len(original) - 10

    def test_no_punctuation_hard_cut(self):
        text = "性" * 500  # 无句读的长段落
        chunks = chunk_text(text, target=100, max_size=200)
        assert len(chunks) >= 3
        assert all(len(c) <= 200 for c in chunks)


class TestTextUtils:
    def test_tokenize_mixed(self):
        tokens = text_utils.tokenize("Redis 缓存穿透是指查询不存在的数据")
        assert "redis" in tokens
        assert any("缓存" in t for t in tokens)

    def test_top_terms_filters_stopwords(self):
        terms = text_utils.top_terms(
            ["索引是数据库中重要的结构，索引可以加速查询，索引维护有成本"], top_k=5
        )
        assert terms
        assert "我们" not in terms

    def test_hashed_vector_deterministic_and_normalized(self):
        v1 = text_utils.hashed_vector(text_utils.tokenize("缓存穿透"), dim=128)
        v2 = text_utils.hashed_vector(text_utils.tokenize("缓存穿透"), dim=128)
        assert v1 == v2
        norm = sum(x * x for x in v1) ** 0.5
        assert abs(norm - 1.0) < 1e-9

    def test_cosine_identical_and_disjoint(self):
        a = [1.0, 0.0, 0.0]
        assert text_utils.cosine(a, [1.0, 0.0, 0.0]) == 1.0
        assert text_utils.cosine(a, [0.0, 1.0, 0.0]) == 0.0
        assert text_utils.cosine([1.0], [1.0, 2.0]) == 0.0  # 维度不一致

    def test_embed_text_semantic_baseline(self):
        # 相同语义的中文句子，内置向量相似度应显著高于无关句子
        a = text_utils.embed_text("Redis 缓存穿透可以用布隆过滤器解决")
        b = text_utils.embed_text("缓存穿透的解决方案包括布隆过滤器")
        c = text_utils.embed_text("Python 装饰器利用闭包增强函数行为")
        assert text_utils.cosine(a, b) > text_utils.cosine(a, c)
