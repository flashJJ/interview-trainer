"""AI 评分服务。

- 选择题：选项字母精确匹配
- 判断题：语义归一化匹配
- 填空题：等价答案包含匹配 → LLM 评判（可选）→ 字符 n-gram TF-IDF 余弦相似度分档
- grade_and_submit_session：整场考试的评分与落库（路由与种子脚本共用）
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from . import text_utils
from .llm_client import LLMClient, extract_json

MAX_SCORE_PER_QUESTION = 10.0
CORRECT_THRESHOLD = 0.6  # 得分率 ≥ 60% 记为正确

# 语义分档阈值不能跨模型通用：哈希向量看字面重合，真实模型看整体语义，
# 后者会把「同领域但答错」也推到 0.5 以上。实测（qwen3-embedding:0.6b，1024 维）：
#   近似「布隆过滤机制 / 布隆过滤器」      0.956 → 应满分
#   相关但错误「缓存空值 / 布隆过滤器」    0.539 → 应 0 分
#   完全无关「TCP 三次握手 / UDP 无连接」 0.678 → 应 0 分
# 所以 api 模式阈值整体上移；local（内置哈希）保持原标定不变。
SEMANTIC_THRESHOLDS = {"api": (0.80, 0.92), "local": (0.50, 0.80)}


def semantic_thresholds(mode: str) -> tuple[float, float]:
    """按 Embedding 实现返回 (半分阈值, 满分阈值)。"""
    return SEMANTIC_THRESHOLDS.get(mode or "local", SEMANTIC_THRESHOLDS["local"])

_TRUE_TOKENS = ("正确", "对", "是", "true", "t", "yes", "y", "√", "✓", "1")
_FALSE_TOKENS = ("错误", "不对", "不正确", "不是", "否", "错", "false", "f", "no", "n", "×", "✗", "0")


@dataclass
class GradeResult:
    score: float
    max_score: float
    is_correct: bool
    feedback: str
    ai_source: str


def normalize_judge_answer(value: str) -> Optional[bool]:
    text = (value or "").strip().lower().replace(" ", "")
    if not text:
        return None
    for tok in _FALSE_TOKENS:
        if tok in text:
            return False
    for tok in _TRUE_TOKENS:
        if tok in text:
            return True
    return None


def extract_choice_letter(value: str) -> str:
    match = re.search(r"[A-Da-d]", (value or "").strip())
    return match.group(0).upper() if match else ""


class Grader:
    def __init__(self, llm: Optional[LLMClient] = None, embeddings=None):
        self.llm = llm
        self.embeddings = embeddings

    # ------------------------------------------------------------------ 单题
    def grade(self, question, user_answer: str) -> GradeResult:
        q_type = question.q_type
        if q_type == "choice":
            return self._grade_choice(question, user_answer)
        if q_type == "judge":
            return self._grade_judge(question, user_answer)
        return self._grade_fill(question, user_answer)

    def _grade_choice(self, question, user_answer: str) -> GradeResult:
        answer = (user_answer or "").strip()
        if not answer:
            return GradeResult(0.0, MAX_SCORE_PER_QUESTION, False, "未作答", "rule")
        correct_letter = extract_choice_letter(question.answer)
        user_letter = extract_choice_letter(answer)
        is_correct = bool(correct_letter) and user_letter == correct_letter
        feedback = "回答正确" if is_correct else f"回答错误，正确答案是 {correct_letter or question.answer}"
        return GradeResult(
            MAX_SCORE_PER_QUESTION if is_correct else 0.0,
            MAX_SCORE_PER_QUESTION,
            is_correct,
            feedback,
            "rule",
        )

    def _grade_judge(self, question, user_answer: str) -> GradeResult:
        answer = (user_answer or "").strip()
        if not answer:
            return GradeResult(0.0, MAX_SCORE_PER_QUESTION, False, "未作答", "rule")
        expected = normalize_judge_answer(question.answer)
        actual = normalize_judge_answer(answer)
        is_correct = expected is not None and actual is not None and expected == actual
        feedback = "回答正确" if is_correct else f"回答错误，正确答案是「{question.answer}」"
        return GradeResult(
            MAX_SCORE_PER_QUESTION if is_correct else 0.0,
            MAX_SCORE_PER_QUESTION,
            is_correct,
            feedback,
            "rule",
        )

    def _grade_fill(self, question, user_answer: str) -> GradeResult:
        answer = (user_answer or "").strip()
        if not answer:
            return GradeResult(0.0, MAX_SCORE_PER_QUESTION, False, "未作答", "rule")

        std = (question.answer or "").strip()
        alternatives = [a.strip() for a in re.split(r"[/|；;，,]", std) if a.strip()] or [std]

        # 1) 等价答案包含匹配
        for alt in alternatives:
            if answer == alt or alt in answer or answer in alt:
                return GradeResult(
                    MAX_SCORE_PER_QUESTION, MAX_SCORE_PER_QUESTION, True, "与标准答案一致", "rule"
                )

        # 2) LLM 评判（可选）
        if self.llm and self.llm.enabled:
            try:
                result = self._llm_grade_fill(question, answer, alternatives)
                if result is not None:
                    return result
            except Exception:  # noqa: BLE001 - LLM 评分失败降级语义相似度
                pass

        # 3) 语义相似度分档
        if self.embeddings:
            similarity = text_utils.cosine(
                self.embeddings.embed(answer), self.embeddings.embed(std)
            )
            half, full = semantic_thresholds(getattr(self.embeddings, "mode", "local"))
            if similarity >= full:
                return GradeResult(
                    MAX_SCORE_PER_QUESTION, MAX_SCORE_PER_QUESTION, True,
                    f"语义匹配度 {similarity:.0%}，与标准答案一致", "rule",
                )
            if similarity >= half:
                return GradeResult(
                    MAX_SCORE_PER_QUESTION / 2, MAX_SCORE_PER_QUESTION, False,
                    f"语义匹配度 {similarity:.0%}，部分正确（标准答案：{std}）", "rule",
                )
            return GradeResult(
                0.0, MAX_SCORE_PER_QUESTION, False,
                f"语义匹配度仅 {similarity:.0%}，与标准答案不符（标准答案：{std}）", "rule",
            )
        return GradeResult(0.0, MAX_SCORE_PER_QUESTION, False, f"与标准答案不符（标准答案：{std}）", "rule")

    def _llm_grade_fill(self, question, user_answer: str, alternatives: list[str]) -> Optional[GradeResult]:
        messages = [
            {
                "role": "system",
                "content": "你是严谨的面试评分官，只输出合法 JSON。",
            },
            {
                "role": "user",
                "content": (
                    "请评判考生的填空题答案。\n"
                    f"题目：{question.content}\n"
                    f"标准答案：{' / '.join(alternatives)}\n"
                    f"考生答案：{user_answer}\n"
                    "评分标准：完全正确 1.0；部分正确（要点不全/表述不全）0.4~0.9；错误 0。"
                    "同义词与表述差异不苛扣分，但核心要点缺失要扣分。\n"
                    "只输出 JSON：{\"score\": 0.8, \"feedback\": \"一句话点评\"}"
                ),
            },
        ]
        data = extract_json(self.llm.chat(messages, temperature=0.1))
        if not isinstance(data, dict):
            return None
        raw_score = float(data.get("score", 0))
        raw_score = min(1.0, max(0.0, raw_score))
        score = round(raw_score * MAX_SCORE_PER_QUESTION, 1)
        feedback = str(data.get("feedback", "")).strip() or "AI 评分完成"
        return GradeResult(
            score,
            MAX_SCORE_PER_QUESTION,
            score >= MAX_SCORE_PER_QUESTION * CORRECT_THRESHOLD,
            feedback,
            "llm",
        )


def grade_and_submit_session(db, session, answers_map: dict[int, str], grader: Grader) -> dict:
    """对整场考试评分并落库。answers_map: {question_id: user_answer}。

    返回与 SubmitExamOut 同构的字典（由路由层转 Pydantic）。
    """
    from ..models import ExamAnswer

    if session.status == "submitted":
        raise ValueError("该考试已提交，不能重复评分")

    # 清理草稿答案（save 端点写入的未评分行），重新写入正式评分
    db.query(ExamAnswer).filter(ExamAnswer.session_id == session.id).delete()
    db.flush()

    items = sorted(session.paper.items, key=lambda i: i.order)
    results = []
    total = 0.0
    max_total = 0.0
    correct_count = 0

    for item in items:
        question = item.question
        user_answer = (answers_map.get(question.id) or "").strip()
        grade = grader.grade(question, user_answer)
        db.add(
            ExamAnswer(
                session_id=session.id,
                question_id=question.id,
                user_answer=user_answer,
                score=grade.score,
                max_score=grade.max_score,
                is_correct=grade.is_correct,
                feedback=grade.feedback,
                ai_source=grade.ai_source,
            )
        )
        total += grade.score
        max_total += grade.max_score
        if grade.is_correct:
            correct_count += 1
        results.append(
            {
                "question_id": question.id,
                "q_type": question.q_type,
                "content": question.content,
                "options": question.options,
                "answer": question.answer,
                "user_answer": user_answer,
                "score": grade.score,
                "max_score": grade.max_score,
                "is_correct": grade.is_correct,
                "feedback": grade.feedback,
                "explanation": question.explanation,
                "ai_source": grade.ai_source,
            }
        )

    submitted_at = datetime.utcnow()
    session.status = "submitted"
    session.submitted_at = submitted_at
    session.total_score = round(total, 1)
    session.max_score = max_total
    session.duration_sec = max(0, int((submitted_at - session.started_at).total_seconds()))
    db.commit()

    # 错题本与 SM-2 排期维护（提交后自动执行）
    from .srs import update_after_submit

    update_after_submit(db, session, results)

    return {
        "session_id": session.id,
        "total_score": session.total_score,
        "max_score": session.max_score,
        "score_rate": round(total / max_total, 3) if max_total else 0.0,
        "correct_count": correct_count,
        "question_count": len(results),
        "duration_sec": session.duration_sec,
        "results": results,
    }
