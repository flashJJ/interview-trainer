import { Card, Statistic } from 'antd'

interface StatCardProps {
  title: string
  value: number | string
  /** 数值颜色（深色系，保证白底可读）；不传则用默认文本色 */
  color?: string
  loading?: boolean
  suffix?: string
}

/** 统计卡：统一卡片容器 + 数值样式规范，避免各页重复写 Card+Statistic。 */
export default function StatCard({ title, value, color, loading, suffix }: StatCardProps) {
  return (
    <Card>
      <Statistic
        title={title}
        value={value}
        suffix={suffix}
        valueStyle={color ? { color } : undefined}
        loading={loading}
      />
    </Card>
  )
}
