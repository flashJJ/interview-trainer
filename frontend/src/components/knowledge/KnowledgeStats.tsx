import { Card, Col, Row, Statistic } from 'antd'
import { BookOutlined } from '@ant-design/icons'
import type { KnowledgeOverview } from '@/api/types'

/** 知识库总览统计卡（4 个指标）。 */
export default function KnowledgeStats({ stats }: { stats: KnowledgeOverview | null }) {
  return (
    <Row gutter={16} style={{ marginBottom: 16 }}>
      <Col span={6}>
        <Card>
          <Statistic title="总条目" value={stats?.entry_count ?? 0} prefix={<BookOutlined />} />
        </Card>
      </Col>
      <Col span={6}>
        <Card>
          <Statistic
            title="已处理"
            value={stats?.ready_count ?? 0}
            valueStyle={{ color: '#3f8600' }}
          />
        </Card>
      </Col>
      <Col span={6}>
        <Card>
          <Statistic title="总块数" value={stats?.chunk_count ?? 0} />
        </Card>
      </Col>
      <Col span={6}>
        <Card>
          <Statistic
            title="向量数"
            value={stats?.vector_count ?? 0}
            suffix={`/ ${stats?.chunk_count ?? 0}`}
          />
        </Card>
      </Col>
    </Row>
  )
}
