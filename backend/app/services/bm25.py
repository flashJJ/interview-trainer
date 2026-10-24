"""BM25 关键词检索（纯 Python，零外部依赖）。

为什么自己写而不是引入 jieba / rank_bm25：
1. 项目的中文分词已经是字符 2/3-gram（见 text_utils.tokenize），BM25 的 term
   直接用同一套 token 即可，中文无需分词器也有可用的召回；
2. 语料规模在百~千块量级，纯 Python 线性打分是微秒级开销，不必上倒排索引库；
3. 少一个依赖就少一个部署/版本风险点（本项目强调零配置可跑）。

BM25 打分（Lucene 变体，idf 恒为正）：
    idf(t) = ln(1 + (N - df + 0.5) / (df + 0.5))
    score(q, d) = Σ_t idf(t) * tf(t,d) * (k1 + 1) / (tf(t,d) + k1 * (1 - b + b * |d| / avgdl))
"""

import math
from collections import Counter

from . import text_utils

DEFAULT_K1 = 1.5
DEFAULT_B = 0.75


class BM25Index:
    """内存 BM25 索引：一次构建，多次查询。

    构建代价与语料总量成正比，因此调用方应按语料版本缓存实例（见 retrieval.py）。
    """

    def __init__(self, docs: list[tuple[int, str]], k1: float = DEFAULT_K1, b: float = DEFAULT_B):
        self.k1 = k1
        self.b = b
        self.ids: list[int] = []
        self._term_freqs: list[Counter] = []
        self._lengths: list[int] = []
        self._df: Counter = Counter()
        self._postings: dict[str, list[int]] = {}

        for doc_id, content in docs:
            tokens = [t for t in text_utils.tokenize(content or "") if not text_utils.is_noise_token(t)]
            if not tokens:
                continue
            idx = len(self.ids)
            tf = Counter(tokens)
            self.ids.append(doc_id)
            self._term_freqs.append(tf)
            self._lengths.append(len(tokens))
            for term in tf:
                self._df[term] += 1
                self._postings.setdefault(term, []).append(idx)

        self._n = len(self.ids)
        self._avgdl = (sum(self._lengths) / self._n) if self._n else 0.0

    def __len__(self) -> int:
        return self._n

    @property
    def vocab_size(self) -> int:
        return len(self._df)

    def _idf(self, term: str) -> float:
        df = self._df.get(term, 0)
        if df == 0:
            return 0.0
        return math.log(1.0 + (self._n - df + 0.5) / (df + 0.5))

    def search(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        """返回 [(chunk_id, score)]，按分数降序；无命中返回空列表。"""
        if self._n == 0 or top_k <= 0:
            return []
        terms = [t for t in text_utils.tokenize(query or "") if not text_utils.is_noise_token(t)]
        if not terms:
            return []
        # 同一 term 在 query 里重复出现时按出现次数加权（BM25 的 qtf 简化处理）
        qtf = Counter(terms)
        scores: dict[int, float] = {}
        for term, weight in qtf.items():
            postings = self._postings.get(term)
            if not postings:
                continue
            idf = self._idf(term)
            for idx in postings:
                tf = self._term_freqs[idx][term]
                dl = self._lengths[idx]
                denom = tf + self.k1 * (1.0 - self.b + self.b * dl / self._avgdl)
                scores[idx] = scores.get(idx, 0.0) + weight * idf * tf * (self.k1 + 1.0) / denom
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        return [(self.ids[idx], round(score, 6)) for idx, score in ranked]
