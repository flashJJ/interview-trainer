// 全局共享的枚举中文映射与格式化工具

import type { Difficulty, EntrySourceType, EntryStatus, QType, QuestionSource } from '../api/types'

export const Q_TYPE_TEXT: Record<QType, string> = {
  choice: '单选题',
  fill: '填空题',
  judge: '判断题',
}

export const DIFFICULTY_TEXT: Record<Difficulty, string> = {
  easy: '简单',
  medium: '中等',
  hard: '困难',
}

export const SOURCE_TYPE_TEXT: Record<EntrySourceType, string> = {
  text: '文本',
  file: '文件',
  url: '网页',
  builtin: '内置',
}

export const ENTRY_STATUS_TEXT: Record<EntryStatus, string> = {
  pending: '待处理',
  processing: '处理中',
  ready: '就绪',
  failed: '失败',
}

export const QUESTION_SOURCE_TEXT: Record<QuestionSource, string> = {
  llm: 'AI 生成',
  rule: '规则生成',
  builtin: '内置精选',
}

/** 题目来源徽标配色 */
export const QUESTION_SOURCE_COLOR: Record<QuestionSource, string> = {
  llm: 'magenta',
  rule: 'default',
  builtin: 'geekblue',
}

/** 知识库来源徽标配色 */
export const SOURCE_TYPE_COLOR: Record<EntrySourceType, string> = {
  text: 'default',
  file: 'blue',
  url: 'cyan',
  builtin: 'geekblue',
}

export const ENTRY_STATUS_COLOR: Record<EntryStatus, string> = {
  pending: 'default',
  processing: 'blue',
  ready: 'green',
  failed: 'red',
}

export const DIFFICULTY_COLOR: Record<Difficulty, string> = {
  easy: 'green',
  medium: 'gold',
  hard: 'red',
}

export const Q_TYPE_COLOR: Record<QType, string> = {
  choice: 'blue',
  fill: 'purple',
  judge: 'cyan',
}

export const QTYPES: QType[] = ['choice', 'fill', 'judge']
export const DIFFICULTIES: Difficulty[] = ['easy', 'medium', 'hard']
export const QUESTION_SOURCES: QuestionSource[] = ['builtin', 'llm', 'rule']

/** ISO 时间格式化为本地可读字符串 */
export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return '-'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(
    d.getMinutes(),
  )}`
}

/** 秒转 分:秒 */
export function fmtDuration(sec: number | null | undefined): string {
  if (sec == null) return '-'
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m} 分 ${String(s).padStart(2, '0')} 秒`
}

/** 0~1 比率转百分比字符串（1 位小数） */
export function pct(rate: number | null | undefined, digits = 1): string {
  if (rate == null || Number.isNaN(rate)) return '-'
  return `${(rate * 100).toFixed(digits)}%`
}

export function truncate(text: string | null | undefined, max: number): string {
  if (!text) return '-'
  return text.length > max ? `${text.slice(0, max)}…` : text
}
