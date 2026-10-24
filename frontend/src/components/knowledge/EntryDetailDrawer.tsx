import { Badge, Descriptions, Drawer, List, Space, Tag, Typography } from 'antd'
import type { KnowledgeEntryDetail } from '@/api/types'
import { fmtTime } from '@/utils/constants'
import { EntryStatusTag } from '@/components/common/StatusTags'

interface EntryDetailDrawerProps {
  detail: KnowledgeEntryDetail | null
  loading: boolean
  onClose: () => void
}

/** 知识库条目详情抽屉：基本信息 + 分块内容与关键词。 */
export default function EntryDetailDrawer({ detail, loading, onClose }: EntryDetailDrawerProps) {
  return (
    <Drawer
      title="知识库详情"
      width={720}
      open={detail !== null}
      onClose={onClose}
      loading={loading}
    >
      {detail && (
        <>
          <Descriptions column={2} size="small" style={{ marginBottom: 16 }}>
            <Descriptions.Item label="标题">{detail.entry.title}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <EntryStatusTag status={detail.entry.status} />
            </Descriptions.Item>
            <Descriptions.Item label="块数">{detail.entry.chunk_count}</Descriptions.Item>
            <Descriptions.Item label="字数">{detail.entry.char_count}</Descriptions.Item>
            <Descriptions.Item label="创建时间" span={2}>
              {fmtTime(detail.entry.created_at)}
            </Descriptions.Item>
            {detail.entry.error && (
              <Descriptions.Item label="错误信息" span={2}>
                <Typography.Text type="danger">{detail.entry.error}</Typography.Text>
              </Descriptions.Item>
            )}
          </Descriptions>
          <Typography.Title level={5}>内容分块（{detail.chunks.length}）</Typography.Title>
          <List
            dataSource={detail.chunks}
            locale={{ emptyText: '暂无分块' }}
            renderItem={(chunk) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <Space size={8}>
                      <Badge count={chunk.seq + 1} color="#2f54eb" />
                      <Typography.Text type="secondary">{chunk.char_count} 字</Typography.Text>
                    </Space>
                  }
                  description={
                    <>
                      <Typography.Paragraph style={{ marginBottom: 8 }}>
                        {chunk.content}
                      </Typography.Paragraph>
                      <Space size={4} wrap>
                        {chunk.keywords.map((kw) => (
                          <Tag key={kw} color="geekblue">
                            {kw}
                          </Tag>
                        ))}
                        {chunk.keywords.length === 0 && (
                          <Typography.Text type="secondary">暂无关键词</Typography.Text>
                        )}
                      </Space>
                    </>
                  }
                />
              </List.Item>
            )}
          />
        </>
      )}
    </Drawer>
  )
}
