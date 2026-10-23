"""规则引擎出题单测：三种题型均能产出结构合法的题目。"""

from app.services.generator import ChunkLike, QuestionGenerator
from app.services.text_utils import top_terms

SAMPLE_CHUNK = (
    "缓存穿透是指查询根本不存在的数据，请求全部落到数据库上。"
    "解决缓存穿透的常用方案是布隆过滤器，它可以在请求到达数据库之前拦截不存在的键。"
    "另一种方案是缓存空值，把不存在的结果也写入缓存并设置较短的过期时间。"
    "缓存击穿是指热点键在过期瞬间承受大量并发请求，可以使用互斥锁来保护数据库。"
)

CORPUS_TERMS = top_terms([SAMPLE_CHUNK], top_k=20)


def make_generator():
    # 无 LLM / 无向量库 => 纯规则引擎 + 无去重
    return QuestionGenerator()


def test_rule_fill_question():
    gen = make_generator()
    draft = gen._generate_one_rule(ChunkLike(id=1, content=SAMPLE_CHUNK), "fill", None, CORPUS_TERMS)
    assert draft is not None
    assert draft.q_type == "fill"
    assert "______" in draft.content
    assert draft.answer and draft.answer in SAMPLE_CHUNK
    assert draft.source == "rule"
    assert draft.keywords


def test_rule_choice_question():
    gen = make_generator()
    draft = gen._generate_one_rule(ChunkLike(id=1, content=SAMPLE_CHUNK), "choice", None, CORPUS_TERMS)
    assert draft is not None
    assert draft.q_type == "choice"
    assert len(draft.options) == 4
    assert draft.answer in "ABCD"
    assert all(opt.startswith(letter + ".") for opt, letter in zip(draft.options, "ABCD"))


def test_rule_judge_question():
    gen = make_generator()
    draft = gen._generate_one_rule(ChunkLike(id=1, content=SAMPLE_CHUNK), "judge", None, CORPUS_TERMS)
    assert draft is not None
    assert draft.q_type == "judge"
    assert draft.answer in ("正确", "错误")
    assert draft.content.startswith("根据资料")


def test_generate_pipeline_produces_all_types():
    gen = make_generator()
    chunks = [ChunkLike(id=i, content=SAMPLE_CHUNK) for i in range(3)]
    outcome = gen.generate(chunks, types=["choice", "fill", "judge"], count_per_type=2, user_id=0)
    types = {d.q_type for d in outcome.drafts}
    assert types == {"choice", "fill", "judge"}
    assert len(outcome.drafts) >= 3
    assert outcome.mode == "rule"
