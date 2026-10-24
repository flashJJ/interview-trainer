import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  App as AntdApp,
  Button,
  Card,
  Col,
  Empty,
  Form,
  InputNumber,
  Modal,
  Progress,
  Row,
  Segmented,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import { AimOutlined, RadarChartOutlined, ThunderboltOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import PageHeader from '@/components/common/PageHeader'
import StatCard from '@/components/common/StatCard'
import { QTYPES, Q_TYPE_TEXT, pct } from '@/utils/constants'
import { stickyTableConfig } from '@/utils/stickyTable'
import type { MasteryDim, MasteryItem, QType } from '@/api/types'
import {
  useMasteryDimension,
  useMasteryOverview,
  useMasteryRadar,
  useMasteryWeakPoints,
  useTargetedExam,
} from '@/hooks/useMastery'

const DIM_OPTIONS: Array<{ label: string; value: MasteryDim }> = [
  { label: '按资料', value: 'entry' },
  { label: '按题型', value: 'q_type' },
  { label: '按难度', value: 'difficulty' },
]

/** 掌握度 → 颜色：薄弱红、一般金、掌握绿，中性值用灰（样本不足） */
function masteryColor(mastery: number, confidence: number): string {
  if (confidence < 0.3) return '#8c8c8c'
  if (mastery < 0.6) return '#cf1322'
  if (mastery < 0.8) return '#d46b08'
  return '#389e0d'
}

interface PracticeForm {
  count: number
  types: QType[]
}

/**
 * 定向练习弹窗。单独成组件：仅在打开时挂载，useForm 创建后立刻连上 Form，
 * 避免「Instance created by useForm is not connected to any Form element」告警。
 */
function PracticeModal({
  item,
  loading,
  onCancel,
  onSubmit,
}: {
  item: MasteryItem
  loading: boolean
  onCancel: () => void
  onSubmit: (values: PracticeForm) => void
}) {
  const [form] = Form.useForm<PracticeForm>()
  const maxCount = Math.max(1, item.question_count)

  return (
    <Modal
      title={`针对性练习 · ${item.dim_label}「${item.label}」`}
      open
      onCancel={onCancel}
      onOk={() => form.submit()}
      okText="组卷并开始"
      confirmLoading={loading}
      destroyOnHidden
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        message={`当前掌握度 ${pct(item.mastery, 0)}，组卷优先取错题本未掌握的题（占比不超过 60%），其次取从未作答的题，最后补足其余；题目不够时会解除占比上限以保证组满。`}
      />
      <Form<PracticeForm>
        form={form}
        layout="vertical"
        initialValues={{ count: Math.min(10, maxCount), types: [...QTYPES] }}
        onFinish={onSubmit}
      >
        <Form.Item
          name="count"
          label={`题目数量（该维度可练 ${item.question_count} 题）`}
          rules={[{ required: true, message: '请输入题目数量' }]}
        >
          <InputNumber min={1} max={maxCount} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item
          name="types"
          label="题型（多选）"
          rules={[{ required: true, message: '请至少选择一种题型' }]}
        >
          <Select
            mode="multiple"
            placeholder="请选择题型"
            options={QTYPES.map((t) => ({ label: Q_TYPE_TEXT[t], value: t }))}
          />
        </Form.Item>
      </Form>
    </Modal>
  )
}

export default function MasteryReport() {
  const { message } = AntdApp.useApp()
  const navigate = useNavigate()

  const [threshold] = useState(0.6)
  const [dim, setDim] = useState<MasteryDim>('entry')
  const [target, setTarget] = useState<MasteryItem | null>(null)

  const overview = useMasteryOverview(threshold)
  const radar = useMasteryRadar()
  const dimensions = useMasteryDimension(dim)
  const weak = useMasteryWeakPoints(threshold, 5)
  const targeted = useTargetedExam()

  const rows = dimensions.data?.items ?? []
  const hasData = (overview.data?.total_answered ?? 0) > 0

  const radarOption = useMemo(() => {
    if (!radar.data) return null
    return {
      tooltip: { trigger: 'item' },
      radar: {
        indicator: radar.data.indicators,
        radius: '68%',
        splitNumber: 4,
        axisName: { color: '#595959', fontSize: 12 },
        splitArea: { areaStyle: { color: ['#fafafa', '#fff'] } },
      },
      series: [
        {
          type: 'radar',
          // 从 0 起：雷达图半径截断会把 40% 和 60% 画得差距悬殊，属于误导
          data: [
            {
              value: radar.data.values,
              name: '掌握度',
              areaStyle: { opacity: 0.25 },
              lineStyle: { width: 2 },
              itemStyle: { color: '#722ed1' },
            },
          ],
        },
      ],
    }
  }, [radar.data])

  const onStartPractice = async (values: PracticeForm) => {
    if (!target) return
    if (!values.types?.length) {
      message.warning('请至少选择一种题型')
      return
    }
    try {
      const paper = await targeted.mutateAsync({
        dim: target.dim,
        key: target.key,
        count: values.count,
        types: values.types,
      })
      message.success(`已生成「${paper.title}」，共 ${paper.question_count} 题`)
      setTarget(null)
      navigate(`/exam/${paper.id}`)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '生成针对性练习失败')
    }
  }

  const columns = [
    {
      title: '维度项',
      dataIndex: 'label',
      key: 'label',
      render: (label: string) => <Typography.Text strong>{label}</Typography.Text>,
    },
    {
      title: '掌握度',
      dataIndex: 'mastery',
      key: 'mastery',
      width: 220,
      render: (mastery: number, record: MasteryItem) => (
        <Tooltip title={`置信度 ${pct(record.confidence)}（累计权重 ${record.weight}）`}>
          <Progress
            percent={Math.round(mastery * 100)}
            size="small"
            strokeColor={masteryColor(mastery, record.confidence)}
            format={() => pct(mastery, 0)}
          />
        </Tooltip>
      ),
    },
    {
      title: '样本',
      key: 'sample',
      width: 130,
      render: (_: unknown, record: MasteryItem) =>
        record.answered > 0 ? (
          <span>
            {record.correct}/{record.answered} 正确
          </span>
        ) : (
          <Typography.Text type="secondary">未观测</Typography.Text>
        ),
    },
    {
      title: '得分率',
      dataIndex: 'avg_score_rate',
      key: 'avg_score_rate',
      width: 100,
      render: (rate: number, record: MasteryItem) =>
        record.answered > 0 ? pct(rate, 0) : '-',
    },
    {
      title: '可练题',
      dataIndex: 'question_count',
      key: 'question_count',
      width: 90,
    },
    {
      title: '错题本',
      dataIndex: 'wrong_pending',
      key: 'wrong_pending',
      width: 100,
      render: (n: number) => (n > 0 ? <Tag color="red">{n} 待消化</Tag> : <span>0</span>),
    },
    {
      title: '操作',
      key: 'action',
      width: 130,
      fixed: 'right' as const,
      render: (_: unknown, record: MasteryItem) => (
        <Button
          type="link"
          size="small"
          icon={<AimOutlined />}
          disabled={record.question_count === 0}
          onClick={() => {
            setTarget(record)
          }}
        >
          针对性练习
        </Button>
      ),
    },
  ]

  return (
    <div>
      <PageHeader icon={<RadarChartOutlined />} title="知识点掌握度" />

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="掌握度口径"
        description={
          <span>
            每次已提交作答记一次观测，按<b>半衰期 14 天</b>做时间衰减（近期表现权重更高）；
            样本不足时掌握度向 <b>50%</b> 收缩并标注置信度，避免把「没练过」误读成「不会」。
            薄弱判定需同时满足：掌握度 &lt; {pct(threshold, 0)}、累计权重 ≥ 1.5、且有题可练。
          </span>
        }
      />

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={12} lg={6}>
          <StatCard
            title="综合掌握度"
            value={pct(overview.data?.overall_mastery ?? 0.5, 0)}
            color={masteryColor(overview.data?.overall_mastery ?? 0.5, overview.data?.confidence ?? 0)}
            loading={overview.isLoading}
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatCard
            title="已作答次数"
            value={overview.data?.total_answered ?? 0}
            suffix="次"
            loading={overview.isLoading}
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatCard
            title="薄弱维度"
            value={overview.data?.weak_count ?? 0}
            color={(overview.data?.weak_count ?? 0) > 0 ? '#cf1322' : '#389e0d'}
            loading={overview.isLoading}
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatCard
            title="错题待消化"
            value={overview.data?.wrong_pending_total ?? 0}
            color={(overview.data?.wrong_pending_total ?? 0) > 0 ? '#d46b08' : undefined}
            loading={overview.isLoading}
          />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={10}>
          <Card title="能力雷达（题型 + 难度）" loading={radar.isLoading}>
            {radarOption ? (
              <ReactECharts option={radarOption} style={{ height: 340 }} notMerge />
            ) : (
              <Empty description="暂无数据" />
            )}
            <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 8 }}>
              未观测的维度显示在中位 50%（灰色不代表薄弱，只代表还没有数据）。
            </Typography.Paragraph>
          </Card>
        </Col>
        <Col xs={24} lg={14}>
          <Card
            title="薄弱项推荐"
            loading={weak.isLoading}
            extra={
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                掌握度升序
              </Typography.Text>
            }
          >
            {weak.data?.items.length ? (
              <Space direction="vertical" style={{ width: '100%' }} size={12}>
                {weak.data.items.map((item) => (
                  <Card key={`${item.dim}-${item.key}`} size="small" styles={{ body: { padding: 12 } }}>
                    <Row align="middle" justify="space-between" wrap={false}>
                      <Col flex="auto" style={{ minWidth: 0 }}>
                        <Space size={8} wrap>
                          <Tag>{item.dim_label}</Tag>
                          <Typography.Text strong ellipsis>
                            {item.label}
                          </Typography.Text>
                          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                            掌握度 {pct(item.mastery, 0)} · 可练 {item.question_count} 题
                            {item.wrong_pending > 0 ? ` · 错题 ${item.wrong_pending}` : ''}
                          </Typography.Text>
                        </Space>
                      </Col>
                      <Col>
                        <Button
                          type="primary"
                          size="small"
                          icon={<ThunderboltOutlined />}
                          loading={targeted.isPending && target?.key === item.key}
                          onClick={() => {
                            setTarget(item)
                          }}
                        >
                          一键练习
                        </Button>
                      </Col>
                    </Row>
                  </Card>
                ))}
              </Space>
            ) : (
              <Empty
                description={
                  hasData ? '当前没有低于阈值的薄弱维度' : '还没有作答数据，先去做一套题'
                }
              />
            )}
          </Card>
        </Col>
      </Row>

      <Card
        style={{ marginTop: 16 }}
        title="维度明细"
        extra={
          <Segmented
            value={dim}
            onChange={(value) => setDim(value as MasteryDim)}
            options={DIM_OPTIONS}
          />
        }
      >
        <Table<MasteryItem>
          rowKey={(record) => `${record.dim}-${record.key}`}
          columns={columns}
          dataSource={rows}
          loading={dimensions.isLoading}
          scroll={{ x: 1000 }}
          sticky={stickyTableConfig}
          pagination={false}
          locale={{ emptyText: '暂无数据' }}
        />
      </Card>

      {target && (
        <PracticeModal
          item={target}
          loading={targeted.isPending}
          onCancel={() => setTarget(null)}
          onSubmit={onStartPractice}
        />
      )}
    </div>
  )
}
