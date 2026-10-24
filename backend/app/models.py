import json
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(120), default="")
    password_hash = Column(String(120), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class SystemConfig(Base):
    """系统配置覆盖项（优先级高于 .env，保存后即时生效，无需重启）。"""

    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    source_type = Column(String(20), default="text")  # text | file
    content = Column(Text, nullable=False)
    status = Column(String(20), default="processing", index=True)  # pending|processing|ready|failed
    error = Column(Text, default="")
    chunk_count = Column(Integer, default=0)
    question_count = Column(Integer, default=0)
    char_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chunks = relationship("KnowledgeChunk", back_populates="entry", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="entry", cascade="all, delete-orphan")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(Integer, primary_key=True)
    entry_id = Column(Integer, ForeignKey("knowledge_entries.id"), nullable=False, index=True)
    seq = Column(Integer, default=0)
    content = Column(Text, nullable=False)
    vector_id = Column(String(64), default="")
    keywords_json = Column("keywords", Text, default="[]")
    char_count = Column(Integer, default=0)

    entry = relationship("KnowledgeEntry", back_populates="chunks")

    @property
    def keywords(self) -> list:
        try:
            return json.loads(self.keywords_json or "[]")
        except (TypeError, ValueError):
            return []


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    entry_id = Column(Integer, ForeignKey("knowledge_entries.id"), nullable=True, index=True)
    chunk_id = Column(Integer, ForeignKey("knowledge_chunks.id"), nullable=True)
    q_type = Column(String(20), nullable=False, index=True)  # choice|fill|judge
    content = Column(Text, nullable=False)
    options_json = Column("options", Text, default="[]")
    answer = Column(Text, nullable=False)
    explanation = Column(Text, default="")
    difficulty = Column(String(20), default="medium", index=True)  # easy|medium|hard
    keywords_json = Column("keywords", Text, default="[]")
    source = Column(String(20), default="rule")  # llm | rule
    review_status = Column(String(20), default="pending", index=True)  # pending | approved | rejected
    vector_id = Column(String(64), default="")
    status = Column(String(20), default="active")  # active | archived
    created_at = Column(DateTime, default=datetime.utcnow)

    entry = relationship("KnowledgeEntry", back_populates="questions")

    @property
    def options(self):
        """选择题选项列表；非选择题返回 None。"""
        try:
            data = json.loads(self.options_json or "[]")
        except (TypeError, ValueError):
            return None
        return data if data else None

    @property
    def keywords(self) -> list:
        try:
            return json.loads(self.keywords_json or "[]")
        except (TypeError, ValueError):
            return []


class ExamPaper(Base):
    __tablename__ = "exam_papers"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    config = Column(Text, default="{}")
    question_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship(
        "ExamPaperQuestion",
        back_populates="paper",
        cascade="all, delete-orphan",
        order_by="ExamPaperQuestion.order",
    )
    sessions = relationship("ExamSession", back_populates="paper")


class ExamPaperQuestion(Base):
    __tablename__ = "exam_paper_questions"

    id = Column(Integer, primary_key=True)
    paper_id = Column(Integer, ForeignKey("exam_papers.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    order = Column(Integer, default=0)

    paper = relationship("ExamPaper", back_populates="items")
    question = relationship("Question")


class ExamSession(Base):
    __tablename__ = "exam_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    paper_id = Column(Integer, ForeignKey("exam_papers.id"), nullable=False, index=True)
    status = Column(String(20), default="in_progress", index=True)  # in_progress | submitted
    mode = Column(String(20), default="exam", index=True)  # exam | review（错题复习）
    started_at = Column(DateTime, default=datetime.utcnow)
    submitted_at = Column(DateTime, nullable=True)
    total_score = Column(Float, default=0.0)
    max_score = Column(Float, default=0.0)
    duration_sec = Column(Integer, default=0)

    paper = relationship("ExamPaper", back_populates="sessions")
    answers = relationship("ExamAnswer", back_populates="session", cascade="all, delete-orphan")


class ExamAnswer(Base):
    __tablename__ = "exam_answers"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("exam_sessions.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    user_answer = Column(Text, default="")
    score = Column(Float, default=0.0)
    max_score = Column(Float, default=10.0)
    is_correct = Column(Boolean, default=False)
    feedback = Column(Text, default="")
    ai_source = Column(String(20), default="rule")  # rule | llm
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ExamSession", back_populates="answers")
    question = relationship("Question")


class AIChatSession(Base):
    """AI 讲题会话（按题目归档，一题可有多个会话）。"""

    __tablename__ = "ai_chat_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    title = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship(
        "AIChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="AIChatMessage.id"
    )
    question = relationship("Question")


class AIChatMessage(Base):
    """AI 讲题消息（user / assistant）。"""

    __tablename__ = "ai_chat_messages"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("ai_chat_sessions.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user | assistant
    content = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("AIChatSession", back_populates="messages")


class WrongQuestion(Base):
    """错题本：答错的题目 + SM-2 间隔重复排期。"""

    __tablename__ = "wrong_questions"
    __table_args__ = (UniqueConstraint("user_id", "question_id", name="uq_wrong_user_question"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    error_count = Column(Integer, default=1)
    last_error_at = Column(DateTime, default=datetime.utcnow)
    easiness = Column(Float, default=2.5)        # SM-2 难易度系数 EF
    interval_days = Column(Integer, default=1)   # 当前复习间隔（天）
    repetitions = Column(Integer, default=0)     # 连续答对次数
    due_date = Column(Date, default=date.today)  # 下次复习日期
    created_at = Column(DateTime, default=datetime.utcnow)

    question = relationship("Question")
