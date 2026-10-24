"""AI 讲题上下文组装单测。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.services.chat_tutor import TUTOR_SYSTEM_PROMPT, build_tutor_messages


def _setup():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    user = models.User(username="u1", password_hash="x")
    db.add(user)
    db.flush()
    entry = models.KnowledgeEntry(user_id=user.id, title="Redis 笔记", content="缓存相关内容")
    db.add(entry)
    db.flush()
    chunk = models.KnowledgeChunk(entry_id=entry.id, seq=0, content="缓存穿透的解决方案是布隆过滤器。")
    db.add(chunk)
    db.flush()
    question = models.Question(
        user_id=user.id,
        entry_id=entry.id,
        chunk_id=chunk.id,
        q_type="choice",
        content="关于缓存穿透，下列说法正确的是？",
        options_json='["A. 布隆过滤器", "B. 互斥锁", "C. 随机TTL", "D. 哨兵模式"]',
        answer="A",
        explanation="布隆过滤器可拦截不存在的键。",
        difficulty="medium",
    )
    db.add(question)
    db.flush()
    return db, question


class TestBuildTutorMessages:
    def test_context_contains_question_and_source(self):
        db, question = _setup()
        messages = build_tutor_messages(db, question, [], user_id=question.user_id)
        system = messages[0]["content"]
        assert TUTOR_SYSTEM_PROMPT in system
        assert "关于缓存穿透" in system          # 题干
        assert "标准答案：A" in system            # 答案
        assert "布隆过滤器可拦截" in system       # 解析
        assert "缓存穿透的解决方案是布隆过滤器" in system  # 出处资料块
        db.close()

    def test_history_appended_in_order(self):
        db, question = _setup()
        history = [
            models.AIChatMessage(session_id=1, role="user", content="第一问"),
            models.AIChatMessage(session_id=1, role="assistant", content="第一答"),
            models.AIChatMessage(session_id=1, role="user", content="第二问"),
        ]
        messages = build_tutor_messages(db, question, history, user_id=question.user_id)
        assert len(messages) == 4  # system + 3 history
        assert messages[1] == {"role": "user", "content": "第一问"}
        assert messages[2] == {"role": "assistant", "content": "第一答"}
        assert messages[3] == {"role": "user", "content": "第二问"}
        db.close()

    def test_last_answer_injected(self):
        db, question = _setup()
        # 构造一次已提交考试且该题答错
        paper = models.ExamPaper(user_id=question.user_id, title="p", question_count=1)
        db.add(paper)
        db.flush()
        session = models.ExamSession(
            user_id=question.user_id, paper_id=paper.id, status="submitted", mode="exam"
        )
        db.add(session)
        db.flush()
        db.add(
            models.ExamAnswer(
                session_id=session.id,
                question_id=question.id,
                user_answer="B",
                score=0,
                max_score=10,
                is_correct=False,
            )
        )
        db.commit()
        messages = build_tutor_messages(db, question, [], user_id=question.user_id)
        system = messages[0]["content"]
        assert "学生最近一次作答" in system and "B" in system
        db.close()

    def test_no_source_chunk_degrades_gracefully(self):
        db, question = _setup()
        question.chunk_id = None
        question.entry_id = None
        db.commit()
        messages = build_tutor_messages(db, question, [], user_id=question.user_id)
        assert "无关联资料" in messages[0]["content"]
        db.close()
