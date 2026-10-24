import type { ReactNode } from 'react'
import { Space, Typography } from 'antd'

interface PageHeaderProps {
  icon?: ReactNode
  title: string
  extra?: ReactNode
}

/** 页面标题区：图标 + 标题 + 右侧操作。 */
export default function PageHeader({ icon, title, extra }: PageHeaderProps) {
  return (
    <Space
      style={{ width: '100%', justifyContent: 'space-between', marginBottom: 8 }}
      align="center"
    >
      <Typography.Title level={4} style={{ margin: 0 }}>
        {icon}
        {icon ? <span style={{ marginLeft: 8 }}>{title}</span> : title}
      </Typography.Title>
      {extra}
    </Space>
  )
}
