import { Tag } from 'antd'
import type { Difficulty } from '@/api/types'
import { DIFFICULTY_COLOR, DIFFICULTY_TEXT } from '@/utils/constants'

/** 难度标签（简单/中等/困难）。 */
export default function DifficultyTag({ difficulty }: { difficulty: Difficulty }) {
  return <Tag color={DIFFICULTY_COLOR[difficulty]}>{DIFFICULTY_TEXT[difficulty]}</Tag>
}
