"""AI 出题引擎。

双通道设计：
- LLM 通道：配置了 OpenAI 兼容 API 时，基于知识块生成高质量题目（严格 JSON + 修复重试）；
- 规则引擎通道：无 API Key 时自动启用，基于术语遮蔽/否定变换生成可演示的题目。

无论哪个通道，产出统一的 DraftQuestion，并经向量去重后入库。
"""

import json
import random
import re
from dataclasses import dataclass, field
from typing import Optional

from ..config import get_settings
from . import text_utils
from .llm_client import LLMClient, extract_json

VALID_TYPES = ("choice", "fill", "judge")
VALID_DIFFICULTY = ("easy", "medium", "hard")

DIFFICULTY_DESC = {
    "easy": "简单（概念记忆层面）",
    "medium": "中等（理解与应用层面）",
    "hard": "困难（综合分析、排查与权衡层面）",
}

TYPE_NAME = {"choice": "单选", "fill": "填空", "judge": "判断"}

SYSTEM_PROMPT = (
    "你是一位资深技术面试官，擅长把技术资料转化为高质量面试题。"
    "铁律：只输出合法 JSON，不输出任何解释文字、不输出 markdown 代码块围栏。"
)

_FILL_BLANK_RE = re.compile(r"_{3,}|（\s*）|\(\s*\)")
_LETTER_RE = re.compile(r"^\s*([A-Da-d])\s*[.、:：]?")


@dataclass
class ChunkLike:
    id: int
    content: str
    entry_id: Optional[int] = None


@dataclass
class DraftQuestion:
    q_type: str
    content: str
    options: list = field(default_factory=list)
    answer: str = ""
    explanation: str = ""
    difficulty: str = "medium"
    keywords: list = field(default_factory=list)
    chunk_id: Optional[int] = None
    entry_id: Optional[int] = None
    source: str = "rule"


@dataclass
class GenerationOutcome:
    drafts: list
    skipped_count: int
    mode: str
    message: str


class QuestionGenerator:
    def __init__(self, llm: LLMClient | None = None, embeddings=None, vector_store=None):
        self.settings = get_settings()
        self.llm = llm
        self.embeddings = embeddings
        self.store = vector_store
        self.mode = "llm" if (llm and llm.enabled) else "rule"

    # ------------------------------------------------------------------ 主入口
    def generate(
        self,
        chunks: list[ChunkLike],
        types: list[str],
        count_per_type: int,
        difficulty: Optional[str] = None,
        user_id: int = 0,
    ) -> GenerationOutcome:
        types = [t for t in types if t in VALID_TYPES] or list(VALID_TYPES)
        if difficulty and difficulty not in VALID_DIFFICULTY:
            difficulty = None
        usable = [c for c in chunks if len((c.content or "").strip()) >= 30]
        if not usable:
            return GenerationOutcome([], 0, self.mode, "可用素材不足：知识块内容太短，无法出题")

        corpus_terms = text_utils.top_terms([c.content for c in usable], top_k=40)

        # 规划任务：每题型从素材池随机取 count_per_type 个块（互不重复，复用同一块时轮转）
        jobs: list[tuple[ChunkLike, str]] = []
        for q_type in types:
            pool_list = list(usable)
            random.shuffle(pool_list)
            for idx in range(count_per_type):
                jobs.append((pool_list[idx % len(pool_list)], q_type))

        # LLM 出题是网络 IO，按任务并发执行（规则引擎模式同样受益）
        results: list[DraftQuestion] = []
        if jobs:
            from concurrent.futures import ThreadPoolExecutor

            max_workers = min(len(jobs), 8)
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = [
                    pool.submit(self._generate_one, chunk, q_type, difficulty, corpus_terms)
                    for chunk, q_type in jobs
                ]
                for future in futures:
                    try:
                        draft = future.result()
                    except Exception:  # noqa: BLE001 - 单任务失败不影响整体
                        draft = None
                    if draft is not None:
                        results.append(draft)

        # 主线程串行去重（Chroma 查询不做并发），并按题型配额收敛
        drafts: list[DraftQuestion] = []
        skipped = 0
        for q_type in types:
            picked = 0
            for draft in [r for r in results if r.q_type == q_type]:
                if picked >= count_per_type:
                    break
                if self._is_duplicate(draft, user_id):
                    skipped += 1
                    continue
                drafts.append(draft)
                picked += 1

        mode_desc = "AI 生成" if self.mode == "llm" else "规则引擎生成"
        parts = [f"{TYPE_NAME[t]}×{sum(1 for d in drafts if d.q_type == t)}" for t in types]
        message = f"已生成 {len(drafts)} 道题（{mode_desc}：{' '.join(parts)}）"
        if skipped:
            message += f"；跳过 {skipped} 道与已有题目重复的题"
        return GenerationOutcome(drafts, skipped, self.mode, message)

    # ------------------------------------------------------------------ 单题生成
    def _generate_one(
        self, chunk: ChunkLike, q_type: str, difficulty: Optional[str], corpus_terms: list[str]
    ) -> Optional[DraftQuestion]:
        draft = None
        if self.mode == "llm":
            try:
                draft = self._generate_one_llm(chunk, q_type, difficulty)
            except Exception:  # noqa: BLE001 - LLM 失败降级规则引擎
                draft = None
        if draft is None:
            draft = self._generate_one_rule(chunk, q_type, difficulty, corpus_terms)
        if draft is not None:
            draft.chunk_id = chunk.id
            draft.entry_id = chunk.entry_id
        return draft

    # ------------------------------------------------------------------ LLM 通道
    def _build_prompt(self, chunk_content: str, q_type: str, difficulty: Optional[str]) -> str:
        level = DIFFICULTY_DESC.get(difficulty, "难度与资料内容匹配（easy/medium/hard 由你判断）")
        base = (
            f"请基于以下技术资料生成 1 道{ TYPE_NAME[q_type] }题。\n\n"
            f"资料：\n\"\"\"\n{chunk_content}\n\"\"\"\n\n"
            f"要求：\n1. 题目必须完全基于资料中的知识点，不得编造资料之外的信息\n"
            f"2. 难度：{level}\n"
            f"3. 附带解析，说明判断依据（可引用资料原文）\n"
        )
        schemas = {
            "choice": (
                "4. 提供 4 个选项（A/B/C/D），有且仅有 1 个正确选项，其余为合理干扰项\n"
                "只输出 JSON：{\"q_type\": \"choice\", \"content\": \"题干\", "
                "\"options\": [\"A. 选项1\", \"B. 选项2\", \"C. 选项3\", \"D. 选项4\"], "
                "\"answer\": \"A\", \"explanation\": \"解析\", \"difficulty\": \"medium\", "
                "\"keywords\": [\"关键词1\", \"关键词2\"]}"
            ),
            "fill": (
                "4. 题干中用 ______ 表示要填的空，空处应填资料中的关键术语或结论\n"
                "只输出 JSON：{\"q_type\": \"fill\", \"content\": \"包含______的题干\", "
                "\"answer\": \"标准答案（多个等价答案用 / 分隔）\", \"explanation\": \"解析\", "
                "\"difficulty\": \"medium\", \"keywords\": [\"关键词1\", \"关键词2\"]}"
            ),
            "judge": (
                "4. 题干是一个完整陈述，答案为\"正确\"或\"错误\"；若为\"错误\"，"
                "题干应是对资料信息的合理篡改（否定、偷换概念、夸大等）\n"
                "只输出 JSON：{\"q_type\": \"judge\", \"content\": \"完整陈述\", "
                "\"answer\": \"正确\", \"explanation\": \"解析\", \"difficulty\": \"medium\", "
                "\"keywords\": [\"关键词1\", \"关键词2\"]}"
            ),
        }
        return base + schemas[q_type]

    def _generate_one_llm(
        self, chunk: ChunkLike, q_type: str, difficulty: Optional[str]
    ) -> Optional[DraftQuestion]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": self._build_prompt(chunk.content, q_type, difficulty)},
        ]
        raw = ""
        for attempt in range(2):  # 失败最多重试一次（推理模型单次耗时长，控制总时长）
            try:
                raw = self.llm.chat(messages, temperature=0.4)
                data = extract_json(raw)
                draft = self._normalize_llm_question(data, q_type, difficulty)
                if draft is not None:
                    return draft
                raise ValueError("字段校验失败")
            except Exception:  # noqa: BLE001
                if attempt == 2:
                    return None
                messages.append({"role": "assistant", "content": raw[:500]})
                messages.append(
                    {
                        "role": "user",
                        "content": "上次输出无法解析或字段不齐。请只输出一个合法 JSON 对象，"
                        "严格按照给定格式，不要输出任何其他文字。",
                    }
                )
        return None

    def _normalize_llm_question(
        self, data, q_type: str, difficulty: Optional[str]
    ) -> Optional[DraftQuestion]:
        if isinstance(data, list):
            data = data[0] if data and isinstance(data[0], dict) else None
        if not isinstance(data, dict):
            return None
        if str(data.get("q_type", q_type)) != q_type:
            return None

        content = str(data.get("content", "")).strip()
        if not (5 <= len(content) <= 600):
            return None
        explanation = str(data.get("explanation", "")).strip() or "依据资料生成。"
        level = str(data.get("difficulty", difficulty or "medium")).strip()
        if level not in VALID_DIFFICULTY:
            level = difficulty or "medium"
        keywords = [str(k).strip() for k in (data.get("keywords") or []) if str(k).strip()][:5]
        if not keywords:
            keywords = text_utils.top_terms([content], top_k=3)

        options: list[str] = []
        answer = str(data.get("answer", "")).strip()

        if q_type == "choice":
            raw_options = data.get("options")
            if not isinstance(raw_options, list) or len(raw_options) != 4:
                return None
            cleaned = []
            for opt in raw_options:
                opt = str(opt).strip()
                opt = re.sub(r"^[A-Da-d]\s*[.、:：]\s*", "", opt)
                if not opt:
                    return None
                cleaned.append(opt)
            letter_match = _LETTER_RE.match(answer)
            if letter_match:
                answer = letter_match.group(1).upper()
            elif answer in cleaned:
                answer = "ABCD"[cleaned.index(answer)]
            else:
                return None
            options = [f"{'ABCD'[i]}. {text}" for i, text in enumerate(cleaned)]

        elif q_type == "fill":
            if not answer:
                return None
            if not _FILL_BLANK_RE.search(content):
                # 模型忘了挖空：尝试把答案替换为空
                if answer in content:
                    content = content.replace(answer, "______", 1)
                else:
                    return None

        elif q_type == "judge":
            answer = "正确" if self._normalize_bool(answer) is True else (
                "错误" if self._normalize_bool(answer) is False else ""
            )
            if not answer:
                return None

        return DraftQuestion(
            q_type=q_type,
            content=content,
            options=options,
            answer=answer,
            explanation=explanation,
            difficulty=level,
            keywords=keywords,
            source="llm",
        )

    @staticmethod
    def _normalize_bool(value) -> Optional[bool]:
        text = str(value).strip().lower().replace(" ", "")
        if not text:
            return None
        for tok in ("错误", "错", "不正确", "不是", "否", "false", "f", "no", "×", "✗", "0"):
            if tok in text:
                return False
        for tok in ("正确", "对", "是", "true", "t", "yes", "y", "√", "✓", "1"):
            if tok in text:
                return True
        return None

    # ------------------------------------------------------------------ 规则引擎通道
    def _generate_one_rule(
        self, chunk: ChunkLike, q_type: str, difficulty: Optional[str], corpus_terms: list[str]
    ) -> Optional[DraftQuestion]:
        sentences = [s.strip() for s in text_utils.split_sentences(chunk.content) if 20 <= len(s.strip()) <= 150]
        if not sentences:
            return None
        level = difficulty or "medium"

        if q_type in ("fill", "choice"):
            candidates = []
            for sentence in sentences:
                for term in corpus_terms:
                    if len(term) >= 2 and term in sentence:
                        candidates.append((sentence, term))
                        break
            if not candidates:
                return None
            random.shuffle(candidates)
            sentence, term = candidates[0]

            if q_type == "fill":
                content = sentence.replace(term, "______", 1)
                return DraftQuestion(
                    q_type="fill",
                    content=content,
                    answer=term,
                    explanation=f"横线处应填入「{term}」。参考原文：{sentence}",
                    difficulty=level,
                    keywords=[term] + [t for t in corpus_terms if t != term][:2],
                    source="rule",
                )

            # choice：术语识别选择题
            distractors = [t for t in corpus_terms if t != term and t not in sentence]
            random.shuffle(distractors)
            pool = [term] + distractors[:3]
            if len(pool) < 4:
                return None
            random.shuffle(pool)
            answer_letter = "ABCD"[pool.index(term)]
            options = [f"{'ABCD'[i]}. {text}" for i, text in enumerate(pool)]
            return DraftQuestion(
                q_type="choice",
                content=f"资料原文：「{sentence.replace(term, '______', 1)}」其中横线处最恰当的术语是？",
                options=options,
                answer=answer_letter,
                explanation=f"正确答案是「{term}」。参考原文：{sentence}",
                difficulty=level,
                keywords=[term] + [t for t in corpus_terms if t != term][:2],
                source="rule",
            )

        if q_type == "judge":
            sentence = random.choice(sentences)
            make_false = random.random() < 0.5
            answer, statement = "正确", sentence
            if make_false:
                for old, new in (
                    ("是指", "不是指"),
                    ("可以", "不可以"),
                    ("能够", "不能够"),
                    ("会", "不会"),
                    ("都", "并非都"),
                    ("是", "不是"),
                ):
                    if old in sentence:
                        statement = sentence.replace(old, new, 1)
                        answer = "错误"
                        break
            return DraftQuestion(
                q_type="judge",
                content=f"根据资料，判断下列说法是否正确：{statement}",
                answer=answer,
                explanation=f"资料原文：{sentence}。上述说法与资料{'相符' if answer == '正确' else '不符'}。",
                difficulty=level,
                keywords=text_utils.top_terms([sentence], top_k=3),
                source="rule",
            )

        return None

    # ------------------------------------------------------------------ 去重
    def _is_duplicate(self, draft: DraftQuestion, user_id: int) -> bool:
        if not self.store:
            return False
        embedding = self.embeddings.embed(draft.content) if self.embeddings else None
        if not embedding:
            return False
        return self.store.max_question_similarity(embedding, user_id) >= self.settings.question_dedup_threshold


def persist_drafts(db, user_id: int, drafts: list[DraftQuestion], embeddings, store, review_status: str = "pending") -> list:
    """把草稿题目写入关系库并同步向量库。返回 Question ORM 对象列表。

    review_status: 新生成题目默认进入待审核（pending）；种子数据等可信来源可传 approved。
    """
    from ..models import Question

    questions: list[Question] = []
    for draft in drafts:
        question = Question(
            user_id=user_id,
            entry_id=draft.entry_id,
            chunk_id=draft.chunk_id,
            q_type=draft.q_type,
            content=draft.content,
            options_json=json.dumps(draft.options, ensure_ascii=False),
            answer=draft.answer,
            explanation=draft.explanation,
            difficulty=draft.difficulty,
            keywords_json=json.dumps(draft.keywords, ensure_ascii=False),
            source=draft.source,
            review_status=review_status,
        )
        db.add(question)
        db.flush()
        vector_id = f"question_{question.id}"
        store.upsert_question(
            vector_id=vector_id,
            question_id=question.id,
            user_id=user_id,
            entry_id=draft.entry_id,
            q_type=draft.q_type,
            content=draft.content,
            embedding=embeddings.embed(draft.content),
        )
        question.vector_id = vector_id
        questions.append(question)
    db.commit()
    return questions


def refresh_entry_question_counts(db, entry_ids) -> None:
    """维护知识条目的题目计数字段（只统计已进入组卷池的 approved 题）。"""
    from ..models import KnowledgeEntry, Question

    for entry_id in {e for e in entry_ids if e}:
        count = (
            db.query(Question)
            .filter(
                Question.entry_id == entry_id,
                Question.status == "active",
                Question.review_status == "approved",
            )
            .count()
        )
        db.query(KnowledgeEntry).filter(KnowledgeEntry.id == entry_id).update(
            {"question_count": count}
        )
    db.commit()
