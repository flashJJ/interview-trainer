"""SM-2 间隔重复算法与错题本维护。

SM-2（SuperMemo 2）是经典的间隔重复调度算法：
- 每次复习后按作答质量 quality（0~5）更新难易度 EF、复习间隔与连续答对次数
- 答对（q>=3）间隔按 1天 -> 6天 -> interval*EF 递增；答错重置为 1 天后重新开始
- EF 随作答质量上下浮动， clamped 在 [1.3, 2.5]
- 连续 3 次答对且间隔 >= 21 天视为掌握，移出错题本
"""

from datetime import date, datetime, timedelta

from ..models import WrongQuestion

DEFAULT_EASINESS = 2.5
MIN_EASINESS = 1.3
MAX_EASINESS = 2.5
MASTER_REPETITIONS = 3      # 连续答对次数达标
MASTER_INTERVAL_DAYS = 21   # 且间隔达到该天数 => 掌握


def quality_from_score(score: float, max_score: float) -> int:
    """把单题得分（0~max）映射为 SM-2 质量分 quality（0~5）。

    >=80% 满分记 5；60%~80% 部分正确记 3~4；<60% 记 0~2。
    """
    if not max_score or max_score <= 0:
        return 0
    rate = max(0.0, min(1.0, score / max_score))
    return max(0, min(5, int(rate * 5 + 0.5)))  # 四舍五入（半分题 => q=3）


def sm2_update(easiness: float, interval_days: int, repetitions: int, quality: int):
    """SM-2 核心递推：返回 (new_easiness, new_interval_days, new_repetitions)。"""
    quality = max(0, min(5, int(quality)))
    if quality >= 3:
        if repetitions == 0:
            interval = 1
        elif repetitions == 1:
            interval = 6
        else:
            interval = max(1, round(interval_days * easiness))
        repetitions += 1
    else:
        repetitions = 0
        interval = 1
    new_easiness = easiness + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.06)
    new_easiness = max(MIN_EASINESS, min(MAX_EASINESS, round(new_easiness, 2)))
    return new_easiness, interval, repetitions


def _apply_review(wrong: WrongQuestion, quality: int) -> None:
    wrong.easiness, wrong.interval_days, wrong.repetitions = sm2_update(
        wrong.easiness, wrong.interval_days, wrong.repetitions, quality
    )
    wrong.due_date = date.today() + timedelta(days=wrong.interval_days)


def update_after_submit(db, session, results: list[dict]) -> None:
    """提交考试/复习后维护错题本。

    results: [{question_id, score, max_score, is_correct}]
    规则：
    - 答错：自动进入错题本（error_count+1），按本次质量分降档重排
    - 复习模式答对：按质量分升档重排；连续 MASTER_REPETITIONS 次答对且
      间隔 >= MASTER_INTERVAL_DAYS 视为掌握，移出错题本
    - 考试模式答对：不影响错题本排期（避免考试反复刷低分题反而推迟复习）
    """
    is_review = getattr(session, "mode", "exam") == "review"
    for item in results:
        question_id = item["question_id"]
        quality = quality_from_score(item.get("score", 0.0), item.get("max_score", 10.0))
        wrong = (
            db.query(WrongQuestion)
            .filter(WrongQuestion.user_id == session.user_id, WrongQuestion.question_id == question_id)
            .first()
        )
        if not item.get("is_correct", False):
            if wrong is None:
                wrong = WrongQuestion(
                    user_id=session.user_id,
                    question_id=question_id,
                    error_count=1,
                    last_error_at=datetime.utcnow(),
                    easiness=DEFAULT_EASINESS,
                    interval_days=1,
                    repetitions=0,
                    due_date=date.today(),
                )
                db.add(wrong)
                db.flush()
            else:
                wrong.error_count += 1
                wrong.last_error_at = datetime.utcnow()
            _apply_review(wrong, quality)
        elif is_review and wrong is not None:
            _apply_review(wrong, quality)
            if (
                wrong.repetitions >= MASTER_REPETITIONS
                and wrong.interval_days >= MASTER_INTERVAL_DAYS
            ):
                db.delete(wrong)  # 掌握：移出错题本
    db.commit()
