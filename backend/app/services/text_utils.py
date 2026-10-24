"""纯文本工具：分词、n-gram TF-IDF 哈希向量、相似度、关键词提取。

这些函数不依赖任何外部服务，是离线向量与语义评分的算法基础，全部可单测。
"""

import hashlib
import math
import re
from collections import Counter

CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
ASCII_WORD_RE = re.compile(r"[a-z][a-z0-9_+#.\-]*")

STOPWORDS = set(
    "的 了 是 在 我 你 他 她 它 们 我们 你们 他们 这 那 这个 那个 这些 那些 就 都 也 和 与 及 或 "
    "而 被 把 让 向 从 到 于 对 为 以 其 之 一个 一些 什么 怎么 怎样 如何 因为 所以 但是 如果 "
    "虽然 并且 或者 还是 就是 不是 不会 没有 可以 可能 应该 需要 通过 进行 实现 使用 如下 以上 "
    "以下 时候 这样 那样 以及 对于 根据 其中 同时 首先 然后 最后 例如 比如 已经 正在 将成为 "
    "来说 而言 一般 通常 常见 主要 基本 之一 不会 不能 不再".split()
)

# 常见的低信息量 n-gram（连接词碎片）
_NOISE_TOKENS = {"其中", "之一", "可以", "我们", "你们", "他们", "这个", "那个", "因此", "但是", "所以", "如果"}


def split_sentences(text: str) -> list[str]:
    """按中文句读切句（保留分隔符语义，仅用于切分）。"""
    parts = re.split(r"(?<=[。！？；!?;])\s*", text.replace("\r\n", "\n"))
    return [p.strip() for p in parts if p.strip()]


def tokenize(text: str) -> list[str]:
    """混合分词：英文/数字词 + 中文连续段的字符 2/3-gram。

    不做依赖分词器的中文分词，靠词频统计让真实术语在排名中胜出。
    """
    tokens: list[str] = []
    tokens.extend(ASCII_WORD_RE.findall(text.lower()))
    for run in CJK_RUN_RE.findall(text):
        if len(run) == 2:
            tokens.append(run)
            continue
        for n in (2, 3):
            for i in range(len(run) - n + 1):
                tokens.append(run[i : i + n])
    return tokens


def _is_noise(tok: str) -> bool:
    if len(tok) < 2:
        return True
    if tok.isdigit():
        return True
    if not re.search(r"[\u4e00-\u9fffA-Za-z]", tok):
        return True
    if tok in STOPWORDS or tok in _NOISE_TOKENS:
        return True
    return False


def is_noise_token(tok: str) -> bool:
    """公开入口：判断 token 是否为无信息量噪声（供 BM25 等检索模块复用）。

    与内部 `_is_noise` 同义，避免跨模块直接引用私有函数。
    """
    return _is_noise(tok)


def top_terms(texts: list[str], top_k: int = 10) -> list[str]:
    """基于词频的关键词提取（跨语料统计，过滤停用词与噪声 n-gram）。"""
    counter: Counter = Counter()
    for text in texts:
        for tok in tokenize(text or ""):
            if not _is_noise(tok):
                counter[tok] += 1
    return [tok for tok, _ in counter.most_common(top_k * 4)][:top_k]


def hashed_vector(tokens: list[str], dim: int = 384) -> list[float]:
    """把词袋哈希为固定维度的 L2 归一化向量（确定性，可复现）。"""
    vec = [0.0] * dim
    for tok in tokens:
        digest = hashlib.md5(tok.encode("utf-8")).hexdigest()
        h = int(digest, 16)
        idx = h % dim
        sign = 1.0 if (h >> 40) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]


def embed_text(text: str, dim: int = 384) -> list[float]:
    return hashed_vector(tokenize(text or ""), dim)


def cosine(a: list[float], b: list[float]) -> float:
    """余弦相似度；长度不一致返回 0。"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)
