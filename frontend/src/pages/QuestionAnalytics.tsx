import { useQuestionAnalytics } from '@/hooks/useAnalytics'
import { Card, Col, Empty, Row, Skeleton, Statistic, Table, Tag, Typography } from 'antd'
import { App as AntdApp } from 'antd'
import ReactECharts from 'echarts-for-react'
import type {
  QuestionAccuracyItem,
  QuestionsAnalyticsOverview,
} from '../api/types'
import { Q_TYPE_COLOR, Q_TYPE_TEXT, pct, truncate } from '../utils/constants'

const DIFFICULTY_TEXT: Record<string, string> = {
  easy: '简单',
  medium: '中等',
  hard: '困难',
}

const DIFFICULTY_COLOR: Record<string, string> = {
  easy: 'green',
  medium: 'gold',
  hard: 'red',
}

export default function QuestionAnalytics() {
  const { message } = AntdApp.useApp()
  // 数据层：TanStack Query 统一管理
  const qa = useQuestionAnalytics(10)
  const overview = qa.overview.data ?? null
  const accuracy = qa.accuracy.data?.items ?? null
  const loading = qa.overview.isLoading || qa.accuracy.isLoading

  const typePieOption = () => {
    const items = (overview?.by_type ?? []).map((d) => ({
      name: Q_TYPE_TEXT[d.key as keyof typeof Q_TYPE_TEXT] ?? d.key,
      value: d.count,
    }))
    const empty = items.reduce((s, i) => s + i.value, 0) === 0
    return {
      title: { text: '题型分布', left: 'center' },
      tooltip: { trigger: 'item', formatter: '{b}: {c} 道（{d}%）' },
      legend: { bottom: 0 },
      series: [
        {
          type: 'pie',
          radius: ['40%', '65%'],
          center: ['50%', '52%'],
          data: empty ? [] : items,
          label: { formatter: '{b}\n{c} 道' },
          emphasis: {
            itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.2)' },
          },
        },
      ],
    }
  }

  const difficultyBarOption = () => {
    const items = overview?.by_difficulty ?? []
    return {
      title: { text: '难度分布', left: 'center' },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { bottom: 0 },
      grid: { left: 56, right: 24, top: 48, bottom: 40 },
      xAxis: {
        type: 'category',
        data: items.map((d) => DIFFICULTY_TEXT[d.key] ?? d.key),
        axisLabel: { interval: 0 },
      },
      yAxis: { type: 'value', minInterval: 1 },
      series: [
        {
          type: 'bar',
          data: items.map((d) => d.count),
          barWidth: '45%',
          itemStyle: { color: '#2f54eb', borderRadius: [4, 4, 0, 0] },
          label: { show: true, position: 'top' },
        },
      ],
    }
  }

  const entryBarOption = () => {
    const items = (overview?.by_entry ?? []).slice(0, 10).reverse()
    return {
      title: { text: '收录量 Top 10 资料', left: 'center' },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { bottom: 0 },
      grid: { left: 8, right: 32, top: 48, bottom: 24, containLabel: true },
      xAxis: { type: 'value', minInterval: 1 },
      yAxis: {
        type: 'category',
        data: items.map((d) => truncate(d.title, 12)),
        axisLabel: { width: 110, overflow: 'truncate' },
      },
      series: [
        {
          type: 'bar',
          data: items.map((d) => d.count),
          barWidth: '55%',
          itemStyle: { color: '#13c2c2', borderRadius: [0, 4, 4, 0] },
          label: { show: true, position: 'right' },
        },
      ],
    }
  }

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card>
            <Statistic title="题目总量" value={overview?.total ?? 0} loading={loading} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="AI 生成数"
              value={overview?.llm_count ?? 0}
              valueStyle={{ color: '#c41d7f' }}
              loading={loading}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="规则生成数"
              value={overview?.rule_count ?? 0}
              valueStyle={{ color: '#595959' }}
              loading={loading}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="已有作答数"
              value={overview?.answered_count ?? 0}
              valueStyle={{ color: '#3f8600' }}
              loading={loading}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card>
            {loading ? (
              <Skeleton active paragraph={{ rows: 6 }} />
            ) : (overview?.by_type ?? []).length === 0 ? (
              <Empty description="暂无数据" />
            ) : (
              <ReactECharts option={typePieOption()} style={{ height: 300 }} notMerge />
            )}
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            {loading ? (
              <Skeleton active paragraph={{ rows: 6 }} />
            ) : (overview?.by_difficulty ?? []).length === 0 ? (
              <Empty description="暂无数据" />
            ) : (
              <ReactECharts option={difficultyBarOption()} style={{ height: 300 }} notMerge />
            )}
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            {loading ? (
              <Skeleton active paragraph={{ rows: 6 }} />
            ) : (overview?.by_entry ?? []).length === 0 ? (
              <Empty description="暂无数据" />
            ) : (
              <ReactECharts option={entryBarOption()} style={{ height: 300 }} notMerge />
            )}
          </Card>
        </Col>
      </Row>

      <Card title="正确率最低的 10 道题">
        <Table<QuestionAccuracyItem>
          rowKey="question_id"
          loading={loading}
          dataSource={accuracy ?? []}
          locale={{ emptyText: '暂无数据' }}
          pagination={false}
          columns={[
            {
              title: '题目内容',
              dataIndex: 'content',
              key: 'content',
              ellipsis: { showTitle: false },
              render: (c: string) => (
                <Typography.Text style={{ maxWidth: 420 }} ellipsis>
                  {truncate(c, 40)}
                </Typography.Text>
              ),
            },
            {
              title: '题型',
              dataIndex: 'q_type',
              key: 'q_type',
              width: 100,
              render: (t: QuestionAccuracyItem['q_type']) => (
                <Tag color={Q_TYPE_COLOR[t]}>{Q_TYPE_TEXT[t]}</Tag>
              ),
            },
            {
              title: '所属资料',
              dataIndex: 'entry_title',
              key: 'entry_title',
              width: 180,
              ellipsis: true,
              render: (t: string | null) => t ?? '-',
            },
            { title: '作答次数', dataIndex: 'answered_count', key: 'answered_count', width: 100 },
            {
              title: '正确率',
              dataIndex: 'accuracy',
              key: 'accuracy',
              width: 120,
              render: (a: number) => (
                <Tag color={a < 0.5 ? 'red' : 'green'}>{pct(a)}</Tag>
              ),
            },
          ]}
        />
      </Card>
    </div>
  )
}
