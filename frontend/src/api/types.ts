// ===== 通用 =====

export interface PageResp<T> {
  items: T[]
  total: number
  page: number
  size: number
}

export interface ApiMessage {
  message: string
}

// ===== 认证 =====

export interface User {
  id: number
  username: string
  email: string | null
  created_at: string
}

export interface LoginResp {
  access_token: string
  token_type: string
  user: User
}

// ===== 知识库 =====

export type EntrySourceType = 'text' | 'file' | 'url'
export type EntryStatus = 'pending' | 'processing' | 'ready' | 'failed'

/** 题目审核状态（v1.2 审核流）。 */
export type ReviewStatus = 'pending' | 'approved' | 'rejected'

export interface KnowledgeEntry {
  id: number
  title: string
  source_type: EntrySourceType
  status: EntryStatus
  error: string | null
  chunk_count: number
  question_count: number
  char_count: number
  created_at: string
  updated_at: string
}

export interface KnowledgeChunk {
  id: number
  seq: number
  content: string
  char_count: number
  keywords: string[]
}

export interface KnowledgeEntryDetail {
  entry: KnowledgeEntry
  chunks: KnowledgeChunk[]
}

export interface SearchResultItem {
  chunk_id: number
  entry_id: number
  entry_title: string
  seq: number
  content: string
  score: number
}

export interface SearchResp {
  results: SearchResultItem[]
}

export interface KnowledgeOverview {
  entry_count: number
  ready_count: number
  processing_count: number
  chunk_count: number
  vector_count: number
}

// ===== 题库 =====

export type QType = 'choice' | 'fill' | 'judge'
export type Difficulty = 'easy' | 'medium' | 'hard'
export type QuestionSource = 'llm' | 'rule'

export interface Question {
  id: number
  q_type: QType
  content: string
  options: string[] | null
  answer: string
  explanation: string
  difficulty: Difficulty
  keywords: string[]
  entry_id: number | null
  entry_title: string | null
  source: QuestionSource
  review_status: ReviewStatus
  created_at: string
}

export interface GenerateQuestionsReq {
  entry_id?: number
  types: QType[]
  count_per_type: number
  difficulty?: Difficulty
}

export interface GenerateQuestionsResp {
  created: Question[]
  created_count: number
  skipped_count: number
  mode: QuestionSource
  message: string
}

export interface QuestionStatsOverview {
  total: number
  approved_count: number
  pending_count: number
  rejected_count: number
  llm_count: number
  rule_count: number
  by_type: Record<string, number>
  by_difficulty: Record<string, number>
  by_entry: Array<{ entry_id: number; title: string; count: number }>
}

// ===== 考试 =====

export interface ExamPaper {
  id: number
  title: string
  question_count: number
  config: {
    count: number
    types: QType[]
    difficulty: Difficulty | null
    entry_ids: number[] | null
  }
  created_at: string
  latest_session: {
    id: number
    status: 'in_progress' | 'submitted'
    total_score: number
    max_score: number
    submitted_at: string | null
  } | null
}

export interface ExamPaperDetail {
  paper: ExamPaper
  questions: ExamQuestion[]
}

export interface ExamQuestion {
  id: number
  q_type: QType
  content: string
  options: string[] | null
  difficulty: Difficulty
}

export interface ExamSession {
  id: number
  paper_id: number
  status: 'in_progress' | 'submitted'
  started_at: string
  submitted_at: string | null
}

export interface StartExamResp {
  session: ExamSession
  questions: ExamQuestion[]
  answers: Array<{ question_id: number; user_answer: string }>
}

export interface SubmitAnswerItem {
  question_id: number
  answer: string
}

export interface SubmitExamReq {
  answers: SubmitAnswerItem[]
}

export interface SubmitResultItem {
  question_id: number
  q_type: QType
  content: string
  options: string[] | null
  answer: string
  user_answer: string | null
  score: number
  max_score: number
  is_correct: boolean
  feedback: string
  explanation: string
  ai_source: QuestionSource
}

export interface SubmitExamResp {
  session_id: number
  total_score: number
  max_score: number
  score_rate: number
  correct_count: number
  question_count: number
  duration_sec: number
  results: SubmitResultItem[]
}

export interface SessionListItem {
  id: number
  paper_title: string
  total_score: number
  max_score: number
  score_rate: number
  correct_count: number
  question_count: number
  duration_sec: number
  submitted_at: string | null
}

export interface SessionDetailResp extends SubmitExamResp {}

// ===== 分析看板 =====

export interface QuestionsAnalyticsOverview {
  total: number
  llm_count: number
  rule_count: number
  answered_count: number
  by_type: Array<{ key: string; count: number }>
  by_difficulty: Array<{ key: string; count: number }>
  by_entry: Array<{ entry_id: number; title: string; count: number }>
}

export interface QuestionAccuracyItem {
  question_id: number
  content: string
  q_type: QType
  entry_title: string | null
  answered_count: number
  correct_count: number
  accuracy: number
}

export interface QuestionAccuracyResp {
  items: QuestionAccuracyItem[]
}

export interface PracticeOverview {
  session_count: number
  submitted_count: number
  avg_score_rate: number
  total_answered: number
  total_correct: number
  overall_accuracy: number
  best_score_rate: number
}

export interface PracticeTrendItem {
  date: string
  session_count: number
  avg_score_rate: number
  answered: number
  correct: number
}

export interface PracticeTrendResp {
  items: PracticeTrendItem[]
}

export interface PracticeByTypeItem {
  q_type: QType
  answered: number
  correct: number
  accuracy: number
  avg_score: number
}

export interface PracticeByTypeResp {
  items: PracticeByTypeItem[]
}

export interface PracticeRecentResp {
  items: SessionListItem[]
}

// ===== 系统配置 =====

export interface SystemConfig {
  llm_base_url: string
  llm_api_key_masked: string
  llm_api_key_set: boolean
  llm_model: string
  llm_timeout_seconds: number
  embedding_base_url: string
  embedding_api_key_masked: string
  embedding_api_key_set: boolean
  embedding_model: string
  llm_enabled: boolean
  embedding_mode: 'api' | 'local'
}

export interface SystemConfigIn {
  llm_base_url?: string | null
  llm_api_key?: string | null
  llm_model?: string | null
  llm_timeout_seconds?: number | null
  embedding_base_url?: string | null
  embedding_api_key?: string | null
  embedding_model?: string | null
}

export interface TestConnectionResult {
  ok: boolean
  latency_ms: number
  detail: string
  error: string
}

// ===== 错题本 =====

export interface WrongQuestionItem {
  id: number
  question_id: number
  content: string
  q_type: QType
  options: string[] | null
  answer: string
  explanation: string
  difficulty: Difficulty
  entry_title: string | null
  error_count: number
  interval_days: number
  repetitions: number
  due_date: string
  days_until_due: number
  last_error_at: string | null
}

export interface WrongQuestionStats {
  total: number
  due_today: number
  overdue: number
  due_next_7_days: number
  by_type: Record<string, number>
}

// ===== AI 讲题 =====

export interface ChatSession {
  id: number
  question_id: number
  title: string
  created_at: string
  updated_at: string | null
}

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  created_at: string
}
