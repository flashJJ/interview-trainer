"""内置内容（知识库语料 + 精选题库）的单测。

覆盖三件事：
1. **语料与题库本身的质量**：条目不重名、题目字段合法、条目引用都能对上、
   题型/难度分布合理、选择题答案可解析。
2. **载入链路**：内置题自动过审、带 builtin 来源标记、能关联到知识库条目。
3. **幂等**：重复载入不会重复写入，但会补齐被删掉的部分。
"""

import pytest

from app.models import KnowledgeEntry, Question, User
from app.services import builtin as builtin_service

from data.builtin import knowledge as knowledge_data
from data.builtin import (
    questions_ai,
    questions_basic,
    questions_db,
    questions_distributed,
    questions_frontend,
    questions_java,
    questions_ops,
    questions_python,
)

QUESTION_MODULES = (
    questions_java,
    questions_python,
    questions_db,
    questions_distributed,
    questions_ai,
    questions_frontend,
    questions_basic,
    questions_ops,
)


def _all_questions():
    specs = []
    for module in QUESTION_MODULES:
        specs.extend(getattr(module, "QUESTIONS", []))
    return specs


# ---------------------------------------------------------------- 语料
class TestBuiltinKnowledge:
    def test_titles_unique(self):
        titles = [e["title"] for e in knowledge_data.BUILTIN_ENTRIES]
        assert len(titles) == len(set(titles))

    def test_every_entry_has_required_fields(self):
        for entry in knowledge_data.BUILTIN_ENTRIES:
            assert entry["domain"] and entry["topic"] and entry["title"]
            assert len(entry["content"]) >= 200, f"{entry['title']} 内容过短"

    def test_covers_backend_and_ai_domains(self):
        domains = {e["domain"] for e in knowledge_data.BUILTIN_ENTRIES}
        # 传统全栈为主（后端 Java/Python、数据层、分布式）+ AI 方向补强
        assert {"后端-Java", "后端-Python", "数据库", "AI 应用"} <= domains


# ---------------------------------------------------------------- 题库内容
class TestBuiltinQuestionBank:
    def test_scale_is_usable_out_of_the_box(self):
        # 开箱即用要求：不配置 LLM 也有足够组卷的题目量
        assert len(_all_questions()) >= 200

    def test_entry_reference_resolvable(self):
        titles = {e["title"] for e in knowledge_data.BUILTIN_ENTRIES}
        for spec in _all_questions():
            assert spec["entry"] in titles, f"题目引用了不存在的条目：{spec['entry']}"

    def test_question_schema_valid(self):
        for spec in _all_questions():
            assert spec["q_type"] in ("choice", "fill", "judge")
            assert spec["difficulty"] in ("easy", "medium", "hard")
            assert len(spec["content"]) >= 10
            assert spec["explanation"], "每道题都要有解析"
            assert spec["keywords"], "每道题都要有关键词"
            if spec["q_type"] == "choice":
                assert len(spec["options"]) == 4
                assert spec["answer"] in ("A", "B", "C", "D")
                prefixes = [o[:2] for o in spec["options"]]
                assert prefixes == ["A.", "B.", "C.", "D."]
            elif spec["q_type"] == "judge":
                assert spec["answer"] in ("正确", "错误")
            else:
                assert "______" in spec["content"]

    def test_contents_unique(self):
        contents = [q["content"] for q in _all_questions()]
        dup = {c for c in contents if contents.count(c) > 1}
        assert not dup, f"题干重复：{list(dup)[:3]}"

    def test_type_and_difficulty_distribution(self):
        specs = _all_questions()
        choice = sum(1 for s in specs if s["q_type"] == "choice")
        hard = sum(1 for s in specs if s["difficulty"] == "hard")
        # 选择题是主力题型；难题要有一定占比，否则区分度不足
        assert choice / len(specs) > 0.5
        assert 0.1 <= hard / len(specs) <= 0.4

    def test_backend_weighted_toward_production(self):
        """后端域（Java/Python/数据层/分布式）应以生产级题目为主。"""
        backend_modules = (questions_java, questions_python, questions_db, questions_distributed)
        specs = []
        for module in backend_modules:
            specs.extend(getattr(module, "QUESTIONS", []))
        hard_or_medium = sum(1 for s in specs if s["difficulty"] in ("medium", "hard"))
        assert hard_or_medium / len(specs) >= 0.7


# ---------------------------------------------------------------- 载入链路
class _RecordingStore:
    """最小向量库替身：只记录写入，不落盘。"""

    def __init__(self):
        self.chunks = []
        self.questions = []

    def upsert_chunk(self, **kwargs):
        self.chunks.append(kwargs)

    def upsert_question(self, **kwargs):
        self.questions.append(kwargs)

    def delete_entry_vectors(self, entry_id):
        return None

    def counts(self):
        return {"chunks": len(self.chunks), "questions": len(self.questions)}


class _LocalEmbeddings:
    mode = "local"

    def embed(self, text: str):
        from app.services import text_utils

        return text_utils.embed_text(text)

    def embed_batch(self, texts):
        return [self.embed(t) for t in texts]


@pytest.fixture()
def patched_builtin(monkeypatch):
    store = _RecordingStore()
    embeddings = _LocalEmbeddings()
    for module in (builtin_service,):
        monkeypatch.setattr(module, "get_embeddings", lambda: embeddings)
        monkeypatch.setattr(module, "get_vector_store", lambda: store)
    # pipeline 内部也从 runtime 取，tests 不走真实向量库
    from app.services import pipeline

    monkeypatch.setattr(pipeline, "get_embeddings", lambda: embeddings)
    monkeypatch.setattr(pipeline, "get_vector_store", lambda: store)
    return store


def make_user(db, name="builtin-tester"):
    user = User(username=name, password_hash="x")
    db.add(user)
    db.flush()
    return user


class TestLoadBuiltin:
    def test_loads_knowledge_and_questions(self, db_session, patched_builtin):
        user = make_user(db_session)
        stat = builtin_service.load_builtin(db_session, user.id, log=lambda _m: None)

        entry_count = (
            db_session.query(KnowledgeEntry)
            .filter(KnowledgeEntry.user_id == user.id)
            .count()
        )
        question_count = (
            db_session.query(Question).filter(Question.user_id == user.id).count()
        )
        assert entry_count == len(knowledge_data.BUILTIN_ENTRIES)
        assert question_count == len(_all_questions())
        assert stat["questions"]["orphan"] == 0, "不应有题目关联不到条目"

    def test_builtin_questions_are_approved_and_tagged(self, db_session, patched_builtin):
        user = make_user(db_session)
        builtin_service.load_builtin(db_session, user.id, log=lambda _m: None)

        rows = db_session.query(Question).filter(Question.user_id == user.id).all()
        assert rows, "应载入内置题目"
        assert {q.source for q in rows} == {"builtin"}
        assert {q.review_status for q in rows} == {"approved"}
        # 每道题都要挂到知识库条目上，掌握度才能按资料聚合
        assert all(q.entry_id is not None for q in rows)

    def test_entries_are_tagged_builtin(self, db_session, patched_builtin):
        user = make_user(db_session)
        builtin_service.load_builtin(db_session, user.id, log=lambda _m: None)
        rows = (
            db_session.query(KnowledgeEntry)
            .filter(KnowledgeEntry.user_id == user.id)
            .all()
        )
        assert {e.source_type for e in rows} == {"builtin"}
        assert all(e.chunk_count > 0 for e in rows)

    def test_idempotent(self, db_session, patched_builtin):
        user = make_user(db_session)
        first = builtin_service.load_builtin(db_session, user.id, log=lambda _m: None)
        second = builtin_service.load_builtin(db_session, user.id, log=lambda _m: None)

        assert first["knowledge"]["created"] == len(knowledge_data.BUILTIN_ENTRIES)
        assert second["knowledge"]["created"] == 0
        assert second["knowledge"]["skipped"] == len(knowledge_data.BUILTIN_ENTRIES)
        assert second["questions"]["created"] == 0
        assert second["questions"]["skipped"] == len(_all_questions())
        assert (
            db_session.query(Question).filter(Question.user_id == user.id).count()
            == len(_all_questions())
        )

    def test_refills_deleted_questions(self, db_session, patched_builtin):
        """删掉一部分内置题后重新载入，应只补齐缺失的部分。"""
        user = make_user(db_session)
        builtin_service.load_builtin(db_session, user.id, log=lambda _m: None)
        target = (
            db_session.query(Question)
            .filter(Question.user_id == user.id, Question.source == "builtin")
            .first()
        )
        db_session.delete(target)
        db_session.commit()

        stat = builtin_service.load_builtin(db_session, user.id, log=lambda _m: None)
        assert stat["questions"]["created"] == 1
        assert stat["questions"]["skipped"] == len(_all_questions()) - 1
        assert (
            db_session.query(Question).filter(Question.user_id == user.id).count()
            == len(_all_questions())
        )
