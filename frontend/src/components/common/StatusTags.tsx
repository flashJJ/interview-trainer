import { Tag } from 'antd'
import type { EntryStatus, ReviewStatus } from '@/api/types'

const ENTRY_STATUS_MAP: Record<EntryStatus, { color: string; text: string }> = {
  pending: { color: 'default', text: '待处理' },
  processing: { color: 'processing', text: '处理中' },
  ready: { color: 'success', text: '就绪' },
  failed: { color: 'error', text: '失败' },
}

const REVIEW_STATUS_MAP: Record<ReviewStatus, { color: string; text: string }> = {
  approved: { color: 'green', text: '已通过' },
  pending: { color: 'orange', text: '待审核' },
  rejected: { color: 'red', text: '已拒绝' },
}

/** 知识条目处理状态标签。 */
export function EntryStatusTag({ status }: { status: EntryStatus }) {
  const item = ENTRY_STATUS_MAP[status] ?? ENTRY_STATUS_MAP.pending
  return <Tag color={item.color}>{item.text}</Tag>
}

/** 题目审核状态标签。 */
export function ReviewStatusTag({ status }: { status: ReviewStatus }) {
  const item = REVIEW_STATUS_MAP[status] ?? REVIEW_STATUS_MAP.approved
  return <Tag color={item.color}>{item.text}</Tag>
}
