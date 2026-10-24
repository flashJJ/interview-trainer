import { useState } from 'react'
import { Badge, Button, Card, Input, List, Space, Tag, Typography } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import type { SearchResultItem } from '@/api/types'
import { pct } from '@/utils/constants'

interface SemanticSearchCardProps {
  results: SearchResultItem[] | null
  loading: boolean
  onSearch: (query: string) => void
}

/** 语义检索卡：输入查询，展示向量检索命中的知识块。 */
export default function SemanticSearchCard({ results, loading, onSearch }: SemanticSearchCardProps) {
  const [query, setQuery] = useState('')

  const trigger = () => onSearch(query.trim())

  return (
    <Card
      title="语义检索"
      size="small"
      style={{ marginBottom: 16 }}
      extra={
        <Space>
          <Input
            placeholder="输入要检索的内容，如：缓存穿透怎么解决"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onPressEnter={trigger}
            style={{ width: 320 }}
            allowClear
          />
          <Button type="primary" icon={<SearchOutlined />} loading={loading} onClick={trigger}>
            检索
          </Button>
        </Space>
      }
    >
      {results === null ? (
        <Typography.Text type="secondary">
          基于向量语义的检索将返回最相关的知识块（Top 5），可查看来源资料、相似度与内容摘要。
        </Typography.Text>
      ) : results.length === 0 ? (
        <Typography.Text type="secondary">暂无检索结果，请尝试其他关键词。</Typography.Text>
      ) : (
        <List
          dataSource={results}
          renderItem={(item) => (
            <List.Item>
              <List.Item.Meta
                title={
                  <Space size={8}>
                    <Tag color="blue">{item.entry_title}</Tag>
                    <Typography.Text type="secondary">块 #{item.seq + 1}</Typography.Text>
                    <Badge count={`相似度 ${pct(item.score)}`} style={{ backgroundColor: '#52c41a' }} />
                  </Space>
                }
                description={
                  <Typography.Paragraph
                    ellipsis={{ rows: 2, expandable: true, symbol: '展开' }}
                    style={{ marginBottom: 0 }}
                  >
                    {item.content}
                  </Typography.Paragraph>
                }
              />
            </List.Item>
          )}
        />
      )}
    </Card>
  )
}
