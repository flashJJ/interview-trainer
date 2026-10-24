import { Tag } from 'antd'
import type { QType } from '@/api/types'
import { Q_TYPE_COLOR, Q_TYPE_TEXT } from '@/utils/constants'

/** 题型标签（单选/填空/判断），全站统一颜色与文案。 */
export default function QTypeTag({ qType }: { qType: QType }) {
  return <Tag color={Q_TYPE_COLOR[qType]}>{Q_TYPE_TEXT[qType]}</Tag>
}
