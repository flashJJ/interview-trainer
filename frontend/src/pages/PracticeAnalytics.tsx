import { usePracticeAnalytics } from '@/hooks/useAnalytics'
import { useWrongStats } from '@/hooks/useWrongQuestions'
import { Card, Col, Empty, Row, Skeleton, Statistic, Table, Tag, Typography } from 'antd'
import { App as AntdApp } from 'antd'
import ReactECharts from 'echarts-for-react'
import type {
  PracticeByTypeItem,
  PracticeOverview,
  PracticeTrendItem,
  SessionListItem,
  WrongQuestionStats,
} from '../api/types'
import { fmtDuration, fmtTime, pct, Q_TYPE_COLOR, Q_TYPE_TEXT } from '../utils/constants'

export default function PracticeAnalytics() {
  const { message } = AntdApp.useApp()
  // 数据层：TanStack Query 统一管理（loading/缓存/失效）
  const practice = usePracticeAnalytics(30, 10)
  const { data: wrongStats } = useWrongStats()
  const overview = practice.overview.data ?? null
  const trend = practice.trend.data?.items ?? null
  const byType = practice.byType.data?.items ?? null
  const recent = practice.recent.data?.items ?? null
  const loading =
    practice.overview.isLoading ||
    practice.trend.isLoading ||
    practice.byType.isLoading ||
    practice.recent.isLoading

  const trendOption = () => {
    const items = trend ?? []
    return {
      title: { text: '近 30 天每日成绩趋势', left: 'center' },
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0, data: ['考试场次', '平均得分率'] },
      grid: { left: 48, right: 56, top: 48, bottom: 48, containLabel: true },
      xAxis: {
        type: 'category',
        data: items.map((d) => d.date),
        axisLabel: { rotate: 45 },
      },
      yAxis: [
        {
          type: 'value',
          name: '场次',
          minInterval: 1,
          position: 'left',
          axisLabel: { formatter: '{value} 场' },
        },
        {
          type: 'value',
          name: '得分率',
          min: 0,
          max: 100,
          position: 'right',
          axisLabel: { formatter: '{value}%' },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: '考试场次',
          type: 'bar',
          data: items.map((d) => d.session_count),
          barWidth: '55%',
          itemStyle: { color: '#2f54eb', borderRadius: [3, 3, 0, 0] },
        },
        {
          name: '平均得分率',
          type: 'line',
          yAxisIndex: 1,
          data: items.map((d) => Number((d.avg_score_rate * 100).toFixed(1))),
          smooth: true,
          symbolSize: 7,
          lineStyle: { width: 3, color: '#fa8c16' },
          itemStyle: { color: '#fa8c16' },
        },
      ],
    }
  }

  const typePieOption = () => {
    const items = (byType ?? []).map((d) => ({
      name: Q_TYPE_TEXT[d.q_type] ?? d.q_type,
      value: d.answered,
    }))
    const total = items.reduce((s, i) => s + i.value, 0)
    return {
      title: { text: '题型作答分布', left: 'center' },
      tooltip: { trigger: 'item', formatter: '{b}: {c} 次（{d}%）' },
      legend: { bottom: 0 },
      series: [
        {
          type: 'pie',
          radius: ['40%', '65%'],
          center: ['50%', '52%'],
          data: total === 0 ? [] : items,
          label: { formatter: '{b}\n{c} 次' },
          emphasis: {
            itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.2)' },
          },
        },
      ],
    }
  }

  const accuracyBarOption = () => {
    const items = byType ?? []
    return {
      title: { text: '各题型正确率', left: 'center' },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: Array<{ name: string; value: number }>) =>
          `${params[0].name}<br/>正确率：${params[0].value}%`,
      },
      legend: { bottom: 0 },
      grid: { left: 48, right: 24, top: 48, bottom: 40 },
      xAxis: {
        type: 'category',
        data: items.map((d) => Q_TYPE_TEXT[d.q_type] ?? d.q_type),
        axisLabel: { interval: 0 },
      },
      yAxis: { type: 'value', min: 0, max: 100, axisLabel: { formatter: '{value}%' } },
      series: [
        {
          type: 'bar',
          data: items.map((d) => Number((d.accuracy * 100).toFixed(1))),
          barWidth: '45%',
          itemStyle: {
            color: '#52c41a',
            borderRadius: [4, 4, 0, 0],
          },
          label: { show: true, position: 'top', formatter: '{c}%' },
        },
      ],
    }
  }

  const noTrend = (trend ?? []).length === 0
  const noByType = (byType ?? []).length === 0

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={24 / 5}>
          <Card>
            <Statistic title="考试场次" value={overview?.session_count ?? 0} loading={loading} />
          </Card>
        </Col>
        <Col span={24 / 5}>
          <Card>
            <Statistic
              title="平均得分率"
              value={pct(overview?.avg_score_rate)}
              valueStyle={{ color: '#2f54eb' }}
              loading={loading}
            />
          </Card>
        </Col>
        <Col span={24 / 5}>
          <Card>
            <Statistic title="累计答题数" value={overview?.total_answered ?? 0} loading={loading} />
          </Card>
        </Col>
        <Col span={24 / 5}>
          <Card>
            <Statistic
              title="综合正确率"
              value={pct(overview?.overall_accuracy)}
              valueStyle={{ color: '#3f8600' }}
              loading={loading}
            />
          </Card>
        </Col>
        <Col span={24 / 5}>
          <Card>
            <Statistic
              title="最佳得分率"
              value={pct(overview?.best_score_rate)}
              valueStyle={{ color: '#fa8c16' }}
              loading={loading}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card>
            <Statistic
              title="错题总数"
              value={wrongStats?.total ?? 0}
              valueStyle={{ color: '#cf1322' }}
              loading={loading}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="今日待复习"
              value={wrongStats?.due_today ?? 0}
              valueStyle={{ color: '#fa8c16' }}
              loading={loading}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="已逾期错题"
              value={wrongStats?.overdue ?? 0}
              valueStyle={{ color: '#cf1322' }}
              loading={loading}
            />
          </Card>
        </Col>
      </Row>

      <Card style={{ marginBottom: 16 }}>
        {loading ? (
          <Skeleton active paragraph={{ rows: 6 }} />
        ) : noTrend ? (
          <Empty description="暂无考试数据" />
        ) : (
          <ReactECharts option={trendOption()} style={{ height: 360 }} notMerge />
        )}
      </Card>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={12}>
          <Card>
            {loading ? (
              <Skeleton active paragraph={{ rows: 6 }} />
            ) : noByType ? (
              <Empty description="暂无数据" />
            ) : (
              <ReactECharts option={typePieOption()} style={{ height: 300 }} notMerge />
            )}
          </Card>
        </Col>
        <Col span={12}>
          <Card>
            {loading ? (
              <Skeleton active paragraph={{ rows: 6 }} />
            ) : noByType ? (
              <Empty description="暂无数据" />
            ) : (
              <ReactECharts option={accuracyBarOption()} style={{ height: 300 }} notMerge />
            )}
          </Card>
        </Col>
      </Row>

      <Card title="最近考试">
        <Table<SessionListItem>
          rowKey="id"
          loading={loading}
          dataSource={recent ?? []}
          locale={{ emptyText: '暂无数据' }}
          pagination={false}
          columns={[
            {
              title: '考卷标题',
              dataIndex: 'paper_title',
              key: 'paper_title',
              ellipsis: true,
              render: (t: string) => <Typography.Text strong>{t}</Typography.Text>,
            },
            {
              title: '得分',
              dataIndex: 'total_score',
              key: 'total_score',
              width: 110,
              render: (v: number, record) => `${v} / ${record.max_score}`,
            },
            {
              title: '得分率',
              dataIndex: 'score_rate',
              key: 'score_rate',
              width: 110,
              render: (v: number) => (
                <Tag color={v >= 0.6 ? 'green' : 'red'}>{pct(v)}</Tag>
              ),
            },
            {
              title: '正确数 / 总数',
              key: 'correct',
              width: 130,
              render: (_, r) => `${r.correct_count} / ${r.question_count}`,
            },
            {
              title: '用时',
              dataIndex: 'duration_sec',
              key: 'duration_sec',
              width: 120,
              render: (v: number) => fmtDuration(v),
            },
            {
              title: '提交时间',
              dataIndex: 'submitted_at',
              key: 'submitted_at',
              width: 170,
              render: fmtTime,
            },
          ]}
        />
      </Card>
    </div>
  )
}
