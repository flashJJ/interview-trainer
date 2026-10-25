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


class KnowledgeUrlIn(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    title: str = ""


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
    mode: str = Field(default="hybrid")  # vector | bm25 | hybrid
    use_rewrite: bool = False


class SearchHit(BaseModel):
    chunk_id: int
    entry_id: int
    entry_title: str
    seq: int
    content: str
    score: float
    vector_score: float = 0.0
    bm25_score: float = 0.0
    channels: List[str] = []


class KnowledgeSearchOut(BaseModel):
    results: List[SearchHit]
    mode: str = "hybrid"
    used_rewrite: bool = False
    elapsed_ms: int = 0


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
    review_status: str = "approved"
    created_at: datetime


class QuestionUpdateIn(BaseModel):
    """编辑题目（审核页「编辑后通过」用）。"""

    content: Optional[str] = None
    options: Optional[List[str]] = None
    answer: Optional[str] = None
    explanation: Optional[str] = None
    difficulty: Optional[str] = None


class ReviewActionIn(BaseModel):
    action: str = "approve"  # approve | reject


class BatchReviewIn(BaseModel):
    question_ids: List[int]
    action: str = "approve"  # approve | reject


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
    focus: str = ""  # 知识点聚焦：非空时用混合检索取材，替代「整篇资料所有块」
    retrieval_top_k: int = Field(default=8, ge=1, le=30)


class RetrievalReceipt(BaseModel):
    """出题取材的检索回执：让「这次题从哪几块来的」可见、可核对。"""

    used: bool
    focus: str = ""
    mode: str = "hybrid"
    hit_count: int = 0
    chunk_ids: List[int] = []


class GenerateQuestionsOut(BaseModel):
    created: List[QuestionOut]
    created_count: int
    skipped_count: int
    mode: str
    message: str
    retrieval: RetrievalReceipt = RetrievalReceipt(used=False)


class QuestionStatsOut(BaseModel):
    total: int
    approved_count: int
    pending_count: int
    rejected_count: int
    llm_count: int
    rule_count: int
    builtin_count: int = 0
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
    builtin_count: int = 0
    pending_count: int
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


# ---------------------------------------------------------------- AI 讲题
class CreateChatSessionIn(BaseModel):
    question_id: int


class ChatSessionOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    question_id: int
    title: str
    created_at: datetime
    updated_at: datetime | None = None


class ChatMessageOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    role: str
    content: str
    created_at: datetime


class SendChatMessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


# ---------------------------------------------------------------- 检索评测
class EvalCaseOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    query: str
    source: str
    origin_chunk_id: int
    note: str
    created_at: datetime
    expected_ids: List[int] = []
    expected_preview: List[str] = []  # 期望块的正文片段，便于前端核对


class EvalCaseCreateIn(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    expected_ids: List[int] = Field(min_length=1)
    note: str = ""


class AutoBuildIn(BaseModel):
    count: int = Field(default=12, ge=3, le=50)
    use_llm: bool = False  # 用 LLM 生成更自然的问题；否则取块内主题句


class AutoBuildOut(BaseModel):
    created: int
    skipped: int
    total_cases: int


class EvalRunIn(BaseModel):
    top_k: int = Field(default=5, ge=1, le=20)
    use_rewrite: bool = False
    include_llm_rewrite: bool = False
    vector_weight: float = Field(default=1.0, ge=0.0, le=2.0)


class ModeMetrics(BaseModel):
    recall: float
    mrr: float
    hit_at_1: float


class EvalCaseResult(BaseModel):
    case_id: int
    query: str
    expected: List[int]
    modes: dict  # {模式: {ranked: [...], recall, mrr, hit1}}


class EvalRunOut(BaseModel):
    id: int
    case_count: int
    top_k: int
    use_rewrite: bool
    vector_weight: float = 1.0
    elapsed_ms: int
    created_at: datetime
    summary: dict
    detail: List[EvalCaseResult] = []


class EvalRunBrief(BaseModel):
    id: int
    case_count: int
    top_k: int
    use_rewrite: bool
    vector_weight: float = 1.0
    elapsed_ms: int
    created_at: datetime
    summary: dict


class EvalOverviewOut(BaseModel):
    case_count: int
    chunk_count: int
    vector_count: int
    latest_run: Optional[EvalRunBrief] = None


class ChunkPickerItem(BaseModel):
    """手工录入评测用例时的知识块候选。"""

    chunk_id: int
    entry_id: int
    entry_title: str
    seq: int
    preview: str


# ---------------------------------------------------------------- 掌握度
class MasteryItem(BaseModel):
    """单个维度键（如「单选」「困难」「某份资料」）的掌握度。"""

    key: str
    label: str
    answered: int = 0
    correct: int = 0
    accuracy: float = 0.0
    avg_score_rate: float = 0.0
    weight: float = 0.0          # 时间衰减后的累计观测权重
    confidence: float = 0.0      # 0~1，样本充分度；低值时 mastery 已被向 0.5 收缩
    mastery: float = 0.5         # 0~1，0.5 表示未观测/样本不足
    question_count: int = 0      # 该维度可练的已审核题数
    wrong_pending: int = 0       # 仍在错题本中未掌握的题数
    dim: str = ""
    dim_label: str = ""


class MasteryDimensionOut(BaseModel):
    dim: str
    dim_label: str
    items: List[MasteryItem]


class MasteryRadarOut(BaseModel):
    indicators: List[dict]  # [{name, max}]：题型 3 轴 + 难度 3 轴
    values: List[float]     # 百分数，与 indicators 一一对应
    groups: List[dict]


class MasteryWeakOut(BaseModel):
    threshold: float
    items: List[MasteryItem]


class MasteryOverviewOut(BaseModel):
    total_answered: int
    total_correct: int
    overall_accuracy: float
    overall_mastery: float
    confidence: float
    weak_count: int
    tested_dimension_count: int
    wrong_pending_total: int
    threshold: float
    top_weak: Optional[MasteryItem] = None


class TargetedExamIn(BaseModel):
    dim: str = Field(default="q_type", pattern="^(q_type|difficulty|entry)$")
    key: str = ""                       # choice/fill/judge、easy/medium/hard 或资料 id
    count: int = Field(default=10, ge=1, le=100)
    types: List[str] = Field(default=["choice", "fill", "judge"])
    title: str = ""
