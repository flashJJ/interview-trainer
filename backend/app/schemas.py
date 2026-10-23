"""Pydantic 出入参模型（API 契约的代码化）。"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- 认证
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=72)
    email: str = ""


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    username: str
    email: str
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------------------------------------------------------------- 知识库
class KnowledgeEntryCreate(BaseModel):
    title: str = ""
    content: str = Field(min_length=30)


class ChunkOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    seq: int
    content: str
    char_count: int
    keywords: List[str]


class KnowledgeEntryOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    title: str
    source_type: str
    status: str
    error: Optional[str] = None
    chunk_count: int
    question_count: int
    char_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None


class KnowledgeDetailOut(BaseModel):
    entry: KnowledgeEntryOut
    chunks: List[ChunkOut]


class KnowledgeListOut(BaseModel):
    items: List[KnowledgeEntryOut]
    total: int
    page: int
    size: int


class KnowledgeSearchIn(BaseModel):
    query: str = Field(min_length=2)
    top_k: int = Field(default=5, ge=1, le=20)


class SearchHit(BaseModel):
    chunk_id: int
    entry_id: int
    entry_title: str
    seq: int
    content: str
    score: float


class KnowledgeSearchOut(BaseModel):
    results: List[SearchHit]


class KnowledgeStatsOut(BaseModel):
    entry_count: int
    ready_count: int
    processing_count: int
    chunk_count: int
    vector_count: int


# ---------------------------------------------------------------- 题目
class QuestionOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    q_type: str
    content: str
    options: Optional[List[str]] = None
    answer: str
    explanation: str
    difficulty: str
    keywords: List[str]
    entry_id: Optional[int] = None
    entry_title: Optional[str] = None
    source: str
    created_at: datetime


class QuestionListOut(BaseModel):
    items: List[QuestionOut]
    total: int
    page: int
    size: int


class GenerateQuestionsIn(BaseModel):
    entry_id: Optional[int] = None
    types: List[str] = Field(default=["choice", "fill", "judge"])
    count_per_type: int = Field(default=3, ge=1, le=10)
    difficulty: Optional[str] = None


class GenerateQuestionsOut(BaseModel):
    created: List[QuestionOut]
    created_count: int
    skipped_count: int
    mode: str
    message: str


class QuestionStatsOut(BaseModel):
    total: int
    llm_count: int
    rule_count: int
    by_type: dict
    by_difficulty: dict
    by_entry: List[dict]


# ---------------------------------------------------------------- 考试
class GenerateExamIn(BaseModel):
    title: str = ""
    count: int = Field(default=10, ge=1, le=100)
    types: List[str] = Field(default=["choice", "fill", "judge"])
    difficulty: Optional[str] = None
    entry_ids: Optional[List[int]] = None


class ExamQuestionOut(BaseModel):
    id: int
    q_type: str
    content: str
    options: Optional[List[str]] = None
    difficulty: str


class ExamPaperOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    title: str
    question_count: int
    config: dict
    created_at: datetime
    latest_session: Optional[dict] = None


class ExamListOut(BaseModel):
    items: List[ExamPaperOut]
    total: int
    page: int
    size: int


class ExamDetailOut(BaseModel):
    paper: ExamPaperOut
    questions: List[ExamQuestionOut]


class ExamSessionOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    paper_id: int
    status: str
    started_at: datetime
    submitted_at: Optional[datetime] = None


class StartExamOut(BaseModel):
    session: ExamSessionOut
    questions: List[ExamQuestionOut]
    answers: List[dict]


class SubmitAnswerIn(BaseModel):
    question_id: int
    answer: str = ""


class SubmitExamIn(BaseModel):
    answers: List[SubmitAnswerIn] = []


class AnswerResultOut(BaseModel):
    question_id: int
    q_type: str
    content: str
    options: Optional[List[str]] = None
    answer: str
    user_answer: str
    score: float
    max_score: float
    is_correct: bool
    feedback: str
    explanation: str
    ai_source: str


class SubmitExamOut(BaseModel):
    session_id: int
    total_score: float
    max_score: float
    score_rate: float
    correct_count: int
    question_count: int
    duration_sec: int
    results: List[AnswerResultOut]


class SessionDetailOut(SubmitExamOut):
    paper_title: str = ""


class SessionListItem(BaseModel):
    id: int
    paper_title: str
    total_score: float
    max_score: float
    score_rate: float
    correct_count: int
    question_count: int
    duration_sec: int
    submitted_at: Optional[datetime] = None


class SessionListOut(BaseModel):
    items: List[SessionListItem]
    total: int
    page: int
    size: int


# ---------------------------------------------------------------- 分析
class KVItem(BaseModel):
    key: str
    count: int


class QuestionsOverviewOut(BaseModel):
    total: int
    llm_count: int
    rule_count: int
    answered_count: int
    by_type: List[KVItem]
    by_difficulty: List[KVItem]
    by_entry: List[dict]


class AccuracyItem(BaseModel):
    question_id: int
    content: str
    q_type: str
    entry_title: Optional[str] = None
    answered_count: int
    correct_count: int
    accuracy: float


class AccuracyOut(BaseModel):
    items: List[AccuracyItem]


class PracticeOverviewOut(BaseModel):
    session_count: int
    submitted_count: int
    avg_score_rate: float
    total_answered: int
    total_correct: int
    overall_accuracy: float
    best_score_rate: float


class TrendItem(BaseModel):
    date: str
    session_count: int
    avg_score_rate: float
    answered: int
    correct: int


class TrendOut(BaseModel):
    items: List[TrendItem]


class ByTypeItem(BaseModel):
    q_type: str
    answered: int
    correct: int
    accuracy: float
    avg_score: float


class ByTypeOut(BaseModel):
    items: List[ByTypeItem]


class RecentOut(BaseModel):
    items: List[SessionListItem]


# ---------------------------------------------------------------- 系统配置
class SystemConfigOut(BaseModel):
    llm_base_url: str
    llm_api_key_masked: str          # 脱敏展示，不回传明文
    llm_api_key_set: bool            # 是否已配置
    llm_model: str
    llm_timeout_seconds: int
    embedding_base_url: str
    embedding_api_key_masked: str
    embedding_api_key_set: bool
    embedding_model: str
    # 当前生效状态
    llm_enabled: bool                # True=AI 模式，False=演示模式
    embedding_mode: str              # api | local


class SystemConfigIn(BaseModel):
    """保存配置：None 表示该字段不修改；空字符串表示清空该项。"""

    llm_base_url: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    llm_timeout_seconds: Optional[int] = None
    embedding_base_url: Optional[str] = None
    embedding_api_key: Optional[str] = None
    embedding_model: Optional[str] = None


class TestConnectionIn(BaseModel):
    target: str = "llm"              # llm | embedding
    llm_base_url: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    embedding_base_url: Optional[str] = None
    embedding_api_key: Optional[str] = None
    embedding_model: Optional[str] = None


class TestConnectionOut(BaseModel):
    ok: bool
    latency_ms: int = 0
    detail: str = ""
    error: str = ""


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=72)


# ---------------------------------------------------------------- 错题本
class WrongQuestionItem(BaseModel):
    id: int
    question_id: int
    content: str
    q_type: str
    options: Optional[List[str]] = None
    answer: str
    explanation: str
    difficulty: str
    entry_title: Optional[str] = None
    error_count: int
    interval_days: int
    repetitions: int
    due_date: date
    days_until_due: int  # 负数表示已逾期
    last_error_at: Optional[datetime] = None


class WrongQuestionListOut(BaseModel):
    items: List[WrongQuestionItem]
    total: int
    page: int
    size: int


class WrongQuestionStatsOut(BaseModel):
    total: int
    due_today: int
    overdue: int
    due_next_7_days: int
    by_type: dict


class ReviewGenerateIn(BaseModel):
    count: int = Field(default=10, ge=1, le=50)
