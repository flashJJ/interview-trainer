"""SM-2 间隔重复算法与错题本维护单测。"""

from datetime import date, timedelta

from app.models import ExamSession, Question, User, WrongQuestion
from app.services.srs import (
    MASTER_INTERVAL_DAYS,
    MASTER_REPETITIONS,
    quality_from_score,
    sm2_update,
    update_after_submit,
)


class TestQualityFromScore:
    def test_full_score(self):
        assert quality_from_score(10, 10) == 5

    def test_partial(self):
        assert quality_from_score(5, 10) == 3  # 半分 => q=3（答对档下限）

    def test_zero(self):
        assert quality_from_score(0, 10) == 0

    def test_invalid_max(self):
        assert quality_from_score(5, 0) == 0


class TestSm2Update:
    def test_first_correct(self):
        ef, interval, rep = sm2_update(2.5, 0, 0, 4)
        assert interval == 1 and rep == 1

    def test_second_correct(self):
        ef, interval, rep = sm2_update(2.5, 1, 1, 5)
        assert interval == 6 and rep == 2

    def test_third_correct_scales_by_ef(self):
        ef, interval, rep = sm2_update(2.5, 6, 2, 5)
        assert interval == round(6 * ef) and rep == 3

    def test_wrong_resets(self):
        ef, interval, rep = sm2_update(2.0, 15, 3, 2)
        assert interval == 1 and rep == 0

    def test_easiness_clamped(self):
        # 连续答得差，EF 不应低于 1.3
        ef, _, _ = sm2_update(1.4, 1, 0, 0)
        assert ef >= 1.3
        # 满分 EF 不超过 2.5
        ef2, _, _ = sm2_update(2.4, 1, 0, 5)
        assert ef2 <= 2.5


class TestUpdateAfterSubmit:
    """集成测试：用内存 SQLite 验证错题收集与复习排期。"""

    def _setup(self, session):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app import models

        engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        user = User(username="u1", password_hash="x")
        db.add(user)
        db.flush()
        entry = None
        question = Question(user_id=user.id, q_type="choice", content="题1", answer="A")
        db.add(question)
        db.flush()
        exam_session = ExamSession(user_id=user.id, paper_id=1, status="submitted", mode=session)
        db.add(exam_session)
        db.flush()
        return db, user, question, exam_session

    def test_wrong_answer_enters_book(self):
        db, user, question, exam_session = self._setup("exam")
        update_after_submit(
            db,
            exam_session,
            [{"question_id": question.id, "score": 0, "max_score": 10, "is_correct": False}],
        )
        wrong = db.query(WrongQuestion).one()
        assert wrong.error_count == 1
        assert wrong.interval_days == 1
        assert wrong.due_date == date.today() + timedelta(days=1)
        db.close()

    def test_repeated_wrong_increments(self):
        db, user, question, exam_session = self._setup("exam")
        for _ in range(3):
            update_after_submit(
                db,
                exam_session,
                [{"question_id": question.id, "score": 0, "max_score": 10, "is_correct": False}],
            )
        wrong = db.query(WrongQuestion).one()
        assert wrong.error_count == 3
        assert wrong.easiness < 2.5  # 连续答错 EF 下降
        db.close()

    def test_review_correct_masters_eventually(self):
        db, user, question, exam_session = self._setup("exam")
        # 先答错入本
        update_after_submit(
            db,
            exam_session,
            [{"question_id": question.id, "score": 0, "max_score": 10, "is_correct": False}],
        )
        # 复习模式连续答对（满分 q=5，EF 很快到 2.5，间隔 1->6->15->...）
        exam_session.mode = "review"
        for i in range(6):
            update_after_submit(
                db,
                exam_session,
                [{"question_id": question.id, "score": 10, "max_score": 10, "is_correct": True}],
            )
            wrong = db.query(WrongQuestion).filter_by(question_id=question.id).first()
            if wrong is None:
                break  # 已掌握移出
            if i == 0:
                assert wrong.repetitions == 1
        # 最终应被移出（连续 3 次答对且间隔 >= 21 天）
        assert db.query(WrongQuestion).count() == 0
        db.close()

    def test_exam_correct_does_not_touch_book(self):
        db, user, question, exam_session = self._setup("exam")
        # 先答错入本
        update_after_submit(
            db,
            exam_session,
            [{"question_id": question.id, "score": 0, "max_score": 10, "is_correct": False}],
        )
        before = db.query(WrongQuestion).one()
        interval_before = before.interval_days
        # 考试模式答对：不动排期
        update_after_submit(
            db,
            exam_session,
            [{"question_id": question.id, "score": 10, "max_score": 10, "is_correct": True}],
        )
        after = db.query(WrongQuestion).one()
        assert after.interval_days == interval_before
        db.close()
