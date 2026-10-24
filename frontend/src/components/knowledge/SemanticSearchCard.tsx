import { useState } from 'react'
import { Button, Card, Input, List, Segmented, Space, Tag, Typography } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import type { RetrievalMode, SearchResultItem } from '@/api/types'
import { pct } from '@/utils/constants'

interface SemanticSearchCardProps {
  results: SearchResultItem[] | null
  loading: boolean
  onSearch: (query: string, mode: RetrievalMode) => void
  /** 本次检索信息（模式/耗时），用于告诉用户"这一条是混合检索的结果" */
  meta?: { mode: string; elapsed_ms: number } | null
}

const MODE_OPTIONS = [
  { label: '混合', value: 'hybrid' as RetrievalMode, title: '向量 + BM25，RRF 融合（推荐）' },
  { label: '向量', value: 'vector' as RetrievalMode, title: '仅语义向量召回' },
  { label: '关键词', value: 'bm25' as RetrievalMode, title: '仅 BM25 关键词召回' },
]

const CHANNEL_LABEL: Record<string, { text: string; color: string }> = {
  vector: { text: '向量', color: 'blue' },
  bm25: { text: 'BM25', color: 'cyan' },
}

/** 检索卡：混合检索（默认）/ 纯向量 / 纯 BM25 三选一，命中结果标注来源通道。 */
export default function SemanticSearchCard({
  results,
  loading,
  onSearch,
  meta,
}: SemanticSearchCardProps) {
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState<RetrievalMode>('hybrid')

  const trigger = () => onSearch(query.trim(), mode)

  return (
    <Card
      title="知识库检索"
      size="small"
      style={{ marginBottom: 16 }}
      extra={
        <Space>
          <Segmented
            size="small"
            value={mode}
            options={MODE_OPTIONS}
            onChange={(v) => setMode(v as RetrievalMode)}
          />
          <Input
            placeholder="输入要检索的内容，如：缓存穿透怎么解决"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onPressEnter={trigger}
            style={{ width: 300 }}
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
          混合检索 = 向量语义召回 + BM25 关键词召回，再用 RRF 按名次融合（默认 Top 5）。
          可切换到单通道对比效果——纯向量擅长"意思相近"，BM25 擅长"术语精确匹配"。
        </Typography.Text>
      ) : results.length === 0 ? (
        <Typography.Text type="secondary">暂无检索结果，请尝试其他关键词。</Typography.Text>
      ) : (
        <>
          {meta && (
            <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
              {MODE_OPTIONS.find((o) => o.value === meta.mode)?.label ?? meta.mode} 检索 ·
              耗时 {meta.elapsed_ms} ms · {results.length} 条命中
            </Typography.Text>
          )}
          <List
            dataSource={results}
            renderItem={(item) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <Space size={8} wrap>
                      <Tag color="blue">{item.entry_title}</Tag>
                      <Typography.Text type="secondary">块 #{item.seq + 1}</Typography.Text>
                      {(item.channels ?? []).map((ch) => (
                        <Tag key={ch} color={CHANNEL_LABEL[ch]?.color ?? 'default'}>
                          {CHANNEL_LABEL[ch]?.text ?? ch}
                        </Tag>
                      ))}
                      {item.vector_score > 0 && (
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          向量 {pct(item.vector_score)}
                        </Typography.Text>
                      )}
                      {item.bm25_score > 0 && (
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          BM25 {item.bm25_score.toFixed(2)}
                        </Typography.Text>
                      )}
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
        </>
      )}
    </Card>
  )
}
