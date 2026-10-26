import { useMemo, useState } from 'react'
import {
  Alert,
  App as AntdApp,
  Button,
  Card,
  Col,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import {
  BarChartOutlined,
  DeleteOutlined,
  ExperimentOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { useQuery } from '@tanstack/react-query'
import { retrievalApi } from '@/api/retrieval'
import type { EvalCase, EvalCaseResult, EvalRunBrief } from '@/api/types'
import {
  useEvalCases,
  useEvalMutations,
  useEvalOverview,
  useEvalRun,
  useEvalRuns,
} from '@/hooks/useRetrieval'
import PageHeader from '@/components/common/PageHeader'
import StatCard from '@/components/common/StatCard'
import { fmtTime, pct } from '@/utils/constants'

/** 图表配色：避免红绿（本项目红涨绿跌约定用于行情，这里只用中性蓝/紫/青） */
const MODE_COLOR: Record<string, string> = {
  vector: '#2f54eb',
  bm25: '#13c2c2',
  hybrid: '#722ed1',
  'hybrid+rewrite': '#fa8c16',
}

const MODE_LABEL: Record<string, string> = {
  vector: '向量',
  bm25: 'BM25',
  hybrid: '混合',
  'hybrid+rewrite': '混合+改写',
}

/** 评测用例来源标签：内置（随系统分发，开箱即用）/ 手工 / 自动生成 */
const CASE_SOURCE_META: Record<string, { text: string; color: string }> = {
  builtin: { text: '内置', color: 'gold' },
  manual: { text: '手工', color: 'green' },
  auto: { text: '自动', color: 'default' },
}

const SEARCH_LIMIT = 200

export default function RetrievalReport() {
  const { message } = AntdApp.useApp()
  const overview = useEvalOverview()
  const cases = useEvalCases()
  const runs = useEvalRuns(10)
  const { autoBuild, createCase, deleteCase, clearCases, loadBuiltinCases, run } = useEvalMutations()

  const [buildForm] = Form.useForm<{ count: number; use_llm: boolean }>()
  const [runForm] = Form.useForm<{
    top_k: number
    use_rewrite: boolean
    vector_weight: number
  }>()
  const [caseForm] = Form.useForm<{ query: string; expected_ids: number[]; note: string }>()

  const [caseModalOpen, setCaseModalOpen] = useState(false)
  const [detailRunId, setDetailRunId] = useState<number | null>(null)

  const detail = useEvalRun(detailRunId)
  const latest = overview.data?.latest_run ?? runs.data?.[0] ?? null

  // 知识块候选（手工录入用例时选期望块；知识库规模小，一次拉全 + 前端过滤）
  const chunkQuery = useQuery({
    queryKey: ['retrieval', 'chunks'],
    queryFn: () => retrievalApi.listChunks(),
    staleTime: 60_000,
    enabled: caseModalOpen,
  })

  const chunkOptions = useMemo(
    () =>
      (chunkQuery.data ?? []).map((c) => ({
        value: c.chunk_id,
        label: `#${c.chunk_id} ${c.entry_title} · 第${c.seq + 1}块 ｜ ${c.preview}`,
      })),
    [chunkQuery.data],
  )

  /** 混合检索相对纯向量的 Recall 提升（百分点） */
  const hybridGain = useMemo(() => {
    if (!latest) return null
    const v = latest.summary?.vector?.recall
    const h = latest.summary?.hybrid?.recall
    if (v == null || h == null) return null
    return h - v
  }, [latest])

  const chartOption = useMemo(() => {
    if (!latest) return null
    const modes = Object.keys(latest.summary)
    const metricMeta = [
      { key: 'recall', name: `Recall@${latest.top_k}` },
      { key: 'mrr', name: 'MRR@10' },
      { key: 'hit_at_1', name: 'Hit@1' },
    ] as const
    return {
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v: number) => pct(v) },
      legend: { bottom: 0 },
      grid: { left: 48, right: 24, top: 32, bottom: 56 },
      xAxis: {
        type: 'category',
        data: modes.map((m) => MODE_LABEL[m] ?? m),
        axisLabel: { color: '#595959' },
      },
      yAxis: {
        type: 'value',
        // 从 0 起：截断纵轴会把 79% 和 86% 的差别画得很夸张，评测报告不能这样误导
        min: 0,
        max: 1,
        axisLabel: { formatter: (v: number) => `${Math.round(v * 100)}%` },
        splitLine: { lineStyle: { type: 'dashed' } },
      },
      series: metricMeta.map((meta) => ({
        name: meta.name,
        type: 'bar',
        barMaxWidth: 42,
        label: {
          show: true,
          position: 'top',
          formatter: (p: { value: number }) => `${(p.value * 100).toFixed(0)}%`,
          fontSize: 11,
        },
        data: modes.map((m) => latest.summary[m]?.[meta.key] ?? 0),
      })),
    }
  }, [latest])

  const onAutoBuild = async () => {
    try {
      const values = await buildForm.validateFields()
      const res = await autoBuild.mutateAsync({ count: values.count, useLlm: values.use_llm })
      if (res.created === 0) {
        message.warning(`没有新增用例（跳过 ${res.skipped} 条），知识块可能已用完`)
      } else {
        message.success(`已生成 ${res.created} 条（跳过 ${res.skipped}），共 ${res.total_cases} 条`)
      }
    } catch (err) {
      if (err instanceof Error) message.error(err.message)
    }
  }

  const onLoadBuiltin = async () => {
    try {
      const res = await loadBuiltinCases.mutateAsync()
      if (res.created === 0) {
        message.info(`内置评测用例已存在（共 ${res.total_cases} 条），无需重复载入`)
      } else {
        message.success(`已载入 ${res.created} 条内置评测用例，共 ${res.total_cases} 条，可直接运行评测`)
      }
    } catch (err) {
      if (err instanceof Error) message.error(err.message)
    }
  }

  const onRun = async () => {
    try {
      const values = await runForm.validateFields()
      const res = await run.mutateAsync({
        top_k: values.top_k,
        use_rewrite: values.use_rewrite,
        vector_weight: values.vector_weight,
      })
      const hybrid = res.summary.hybrid
      message.success(
        `评测完成：${res.case_count} 条用例，混合检索 Recall@${res.top_k} = ${pct(hybrid?.recall)}`,
      )
      setDetailRunId(res.id)
    } catch (err) {
      if (err instanceof Error) message.error(err.message)
    }
  }

  const runColumns = [
    { title: '运行', dataIndex: 'id', key: 'id', width: 64, render: (v: number) => `#${v}` },
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 150,
      render: (v: string) => fmtTime(v),
    },
    {
      title: '用例',
      dataIndex: 'case_count',
      key: 'case_count',
      width: 70,
      align: 'right' as const,
    },
    {
      title: '参数',
      key: 'params',
      width: 190,
      render: (_: unknown, r: EvalRunBrief) => (
        <Space size={4} wrap>
          <Tag>top{ r.top_k }</Tag>
          <Tag color={r.vector_weight < 1 ? 'orange' : 'default'}>w={r.vector_weight}</Tag>
          {r.use_rewrite && <Tag color="purple">改写</Tag>}
        </Space>
      ),
    },
    {
      title: '向量 R@K',
      key: 'vector',
      width: 96,
      align: 'right' as const,
      render: (_: unknown, r: EvalRunBrief) => pct(r.summary?.vector?.recall),
    },
    {
      title: 'BM25 R@K',
      key: 'bm25',
      width: 96,
      align: 'right' as const,
      render: (_: unknown, r: EvalRunBrief) => pct(r.summary?.bm25?.recall),
    },
    {
      title: '混合 R@K',
      key: 'hybrid',
      width: 96,
      align: 'right' as const,
      render: (_: unknown, r: EvalRunBrief) => (
        <Typography.Text strong>{pct(r.summary?.hybrid?.recall)}</Typography.Text>
      ),
    },
    {
      title: '混合 Hit@1',
      key: 'hit1',
      width: 100,
      align: 'right' as const,
      render: (_: unknown, r: EvalRunBrief) => pct(r.summary?.hybrid?.hit_at_1),
    },
    {
      title: '耗时',
      dataIndex: 'elapsed_ms',
      key: 'elapsed_ms',
      width: 86,
      align: 'right' as const,
      render: (v: number) => `${v} ms`,
    },
    {
      title: '操作',
      key: 'action',
      width: 90,
      fixed: 'right' as const,
      render: (_: unknown, r: EvalRunBrief) => (
        <Button type="link" size="small" onClick={() => setDetailRunId(r.id)}>
          明细
        </Button>
      ),
    },
  ]

  const caseColumns = [
    {
      title: '查询',
      dataIndex: 'query',
      key: 'query',
      ellipsis: true,
      render: (v: string) => <Typography.Text copyable>{v}</Typography.Text>,
    },
    {
      title: '期望块',
      key: 'expected',
      width: 260,
      render: (_: unknown, r: EvalCase) => (
        <Space size={4} wrap>
          {r.expected_ids.map((id, i) => (
            <Tooltip key={id} title={r.expected_preview[i] ?? `块 #${id}`}>
              <Tag color="blue">#{id}</Tag>
            </Tooltip>
          ))}
        </Space>
      ),
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 90,
      render: (v: string) => {
        const m = CASE_SOURCE_META[v] ?? { text: v, color: 'default' }
        return <Tag color={m.color}>{m.text}</Tag>
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 90,
      fixed: 'right' as const,
      render: (_: unknown, r: EvalCase) => (
        <Popconfirm
          title="删除该用例"
          onConfirm={async () => {
            try {
              await deleteCase.mutateAsync(r.id)
              message.success('已删除')
            } catch (err) {
              if (err instanceof Error) message.error(err.message)
            }
          }}
          okText="删除"
          cancelText="取消"
        >
          <Button type="link" size="small" danger icon={<DeleteOutlined />}>
            删除
          </Button>
        </Popconfirm>
      ),
    },
  ]

  const detailRows: EvalCaseResult[] = detail.data?.detail ?? []

  return (
    <div>
      <PageHeader
        icon={<ExperimentOutlined />}
        title="检索评测"
        extra={
          <Typography.Text type="secondary">
            量化「混合检索到底有没有用」，而不是凭感觉
          </Typography.Text>
        }
      />

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="评测口径"
        description={
          <div style={{ lineHeight: 1.8 }}>
            用同一批「查询 → 期望知识块」用例，分别跑纯向量、纯 BM25、混合（RRF 融合）三种模式，
            对比 Recall@K、MRR@10、Hit@1。
            <br />
            <strong>已知局限</strong>：自动生成的查询由 LLM 对知识块改述而来，仍存在语料内同源泄漏，
            指标绝对值偏乐观，<strong>请横向比较同一行的相对差异</strong>；需要严格口径时请手工录入真实提问。
          </div>
        }
      />

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} md={6}>
          <StatCard title="评测用例" value={overview.data?.case_count ?? 0} suffix="条" loading={overview.isLoading} />
        </Col>
        <Col xs={12} md={6}>
          <StatCard
            title="知识块 / 已建向量"
            value={`${overview.data?.chunk_count ?? 0} / ${overview.data?.vector_count ?? 0}`}
            loading={overview.isLoading}
          />
        </Col>
        <Col xs={12} md={6}>
          <StatCard
            title="最近 混合 Recall@K"
            value={latest ? pct(latest.summary?.hybrid?.recall) : '-'}
            color="#722ed1"
            loading={overview.isLoading}
          />
        </Col>
        <Col xs={12} md={6}>
          <StatCard
            title="混合相对纯向量"
            value={hybridGain == null ? '-' : `${hybridGain >= 0 ? '+' : ''}${(hybridGain * 100).toFixed(1)}`}
            suffix={hybridGain == null ? undefined : 'pt'}
            color={hybridGain != null && hybridGain > 0 ? '#237804' : undefined}
          />
        </Col>
      </Row>

      <Card title="操作" style={{ marginBottom: 16 }}>
        <Row gutter={[24, 16]}>
          <Col xs={24} lg={11}>
            <Typography.Text strong>评测集</Typography.Text>
            <Form form={buildForm} layout="inline" style={{ marginTop: 8 }} initialValues={{ count: 12, use_llm: true }}>
              <Form.Item name="count" label="数量">
                <InputNumber min={3} max={50} style={{ width: 80 }} />
              </Form.Item>
              <Form.Item
                name="use_llm"
                label="LLM 改述"
                valuePropName="checked"
                tooltip="开启后用模型把知识块改写成自然提问（更接近真实使用，但每条需几秒）；关闭则用关键词拼接（快，但指标会虚高）"
              >
                <Switch size="small" />
              </Form.Item>
              <Form.Item>
                <Space>
                  <Button
                    type="primary"
                    icon={<ThunderboltOutlined />}
                    loading={autoBuild.isPending}
                    onClick={() => void onAutoBuild()}
                  >
                    自动生成
                  </Button>
                  <Popconfirm
                    title="清空全部评测用例？"
                    description="历史运行记录会保留，但无法再用旧用例复现。"
                    onConfirm={async () => {
                      try {
                        const r = await clearCases.mutateAsync()
                        message.success(`已清空 ${r.deleted} 条`)
                      } catch (err) {
                        if (err instanceof Error) message.error(err.message)
                      }
                    }}
                    okText="清空"
                    cancelText="取消"
                  >
                    <Button danger disabled={(overview.data?.case_count ?? 0) === 0}>
                      清空
                    </Button>
                  </Popconfirm>
                  <Button
                    icon={<PlusOutlined />}
                    onClick={() => {
                      caseForm.resetFields()
                      setCaseModalOpen(true)
                    }}
                  >
                    手工新增
                  </Button>
                  <Button
                    icon={<ExperimentOutlined />}
                    loading={loadBuiltinCases.isPending}
                    onClick={() => void onLoadBuiltin()}
                  >
                    载入内置用例
                  </Button>
                </Space>
              </Form.Item>
            </Form>
            {autoBuild.isPending && (
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                正在逐块调用 LLM 改写查询，通常需要 1~3 分钟，请勿关闭页面…
              </Typography.Text>
            )}
          </Col>
          <Col xs={24} lg={13}>
            <Typography.Text strong>运行评测</Typography.Text>
            <Form
              form={runForm}
              layout="inline"
              style={{ marginTop: 8 }}
              initialValues={{ top_k: 5, use_rewrite: true, vector_weight: 1 }}
            >
              <Form.Item name="top_k" label="top K">
                <InputNumber min={1} max={20} style={{ width: 70 }} />
              </Form.Item>
              <Form.Item
                name="vector_weight"
                label="向量权重"
                tooltip="RRF 融合中向量通道的权重（BM25 恒为 1）。内置词法向量较弱时下调可减少其拖累，用评测集实测决定"
              >
                <Select
                  style={{ width: 96 }}
                  options={[
                    { value: 1, label: '1.0' },
                    { value: 0.8, label: '0.8' },
                    { value: 0.5, label: '0.5' },
                    { value: 0.3, label: '0.3' },
                  ]}
                />
              </Form.Item>
              <Form.Item name="use_rewrite" label="查询改写" valuePropName="checked">
                <Switch size="small" />
              </Form.Item>
              <Form.Item>
                <Button
                  type="primary"
                  icon={<PlayCircleOutlined />}
                  loading={run.isPending}
                  disabled={(overview.data?.case_count ?? 0) === 0}
                  onClick={() => void onRun()}
                >
                  运行评测
                </Button>
              </Form.Item>
            </Form>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              三档基线永远不开改写，改写档单独比较；向量/BM25 是单通道，权重不影响它们。
            </Typography.Text>
          </Col>
        </Row>
      </Card>

      <Card
        title={
          <Space>
            <BarChartOutlined />
            指标对比
          </Space>
        }
        extra={
          latest ? (
            <Space size={6}>
              <Tag>top{latest.top_k}</Tag>
              <Tag color={latest.vector_weight < 1 ? 'orange' : 'default'}>
                w={latest.vector_weight}
              </Tag>
              {latest.use_rewrite && <Tag color="purple">含改写档</Tag>}
              <Typography.Text type="secondary">
                run #{latest.id} · {fmtTime(latest.created_at)} · {latest.case_count} 条用例
              </Typography.Text>
            </Space>
          ) : null
        }
        style={{ marginBottom: 16 }}
      >
        {chartOption ? (
          <ReactECharts option={chartOption} style={{ height: 300 }} notMerge />
        ) : (
          <Empty description="还没有评测数据，先生成评测集并运行一次评测" />
        )}
      </Card>

      <Card title="评测历史" style={{ marginBottom: 16 }}>
        <Table<EvalRunBrief>
          rowKey="id"
          size="small"
          loading={runs.isLoading}
          columns={runColumns}
          dataSource={runs.data ?? []}
          scroll={{ x: 1080 }}
          pagination={false}
          locale={{ emptyText: '暂无运行记录' }}
        />
      </Card>

      <Card title={`评测集（${cases.data?.length ?? 0} 条）`}>
        <Table<EvalCase>
          rowKey="id"
          size="small"
          loading={cases.isLoading}
          columns={caseColumns}
          dataSource={cases.data ?? []}
          scroll={{ x: 800 }}
          pagination={{ pageSize: 10, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
          locale={{ emptyText: '暂无评测用例' }}
        />
      </Card>

      <Modal
        title="新增评测用例"
        open={caseModalOpen}
        onCancel={() => setCaseModalOpen(false)}
        onOk={async () => {
          try {
            const values = await caseForm.validateFields()
            await createCase.mutateAsync(values)
            message.success('已新增')
            setCaseModalOpen(false)
          } catch (err) {
            if (err instanceof Error) message.error(err.message)
          }
        }}
        confirmLoading={createCase.isPending}
        okText="保存"
        cancelText="取消"
        width={680}
        forceRender
      >
        <Form form={caseForm} layout="vertical">
          <Form.Item
            name="query"
            label="查询"
            rules={[{ required: true, min: 2, message: '请填写至少 2 个字符的查询' }]}
          >
            <Input placeholder="用真实用户会怎么问来写，例如：Redis 为什么用单线程还这么快？" />
          </Form.Item>
          <Form.Item
            name="expected_ids"
            label="期望命中的知识块（可多选）"
            rules={[{ required: true, message: '至少选择一个期望块' }]}
            tooltip={`候选来自你的知识库（最多 ${SEARCH_LIMIT} 块），支持按内容搜索`}
          >
            <Select
              mode="multiple"
              showSearch
              optionFilterProp="label"
              placeholder="搜索并选择知识块"
              loading={chunkQuery.isLoading}
              options={chunkOptions}
              maxTagCount={3}
            />
          </Form.Item>
          <Form.Item name="note" label="备注">
            <Input.TextArea rows={2} placeholder="可选：这条用例想验证什么" />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer
        title={detail.data ? `评测明细 · run #${detail.data.id}` : '评测明细'}
        open={detailRunId !== null}
        onClose={() => setDetailRunId(null)}
        width={760}
        destroyOnClose
      >
        {detail.isLoading ? (
          <Empty description="加载中…" />
        ) : detailRows.length === 0 ? (
          <Empty description="没有明细数据" />
        ) : (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            {detailRows.map((row) => (
              <Card key={row.case_id} size="small" styles={{ body: { padding: 12 } }}>
                <div style={{ marginBottom: 8 }}>
                  <Typography.Text strong>{row.query}</Typography.Text>
                  <div style={{ marginTop: 4 }}>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      期望块：
                    </Typography.Text>
                    {row.expected.map((id) => (
                      <Tag key={id} color="blue">
                        #{id}
                      </Tag>
                    ))}
                  </div>
                </div>
                {Object.entries(row.modes).map(([mode, m]) => (
                  <div key={mode} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                    <Tag color={MODE_COLOR[mode] ? undefined : 'default'} style={{ minWidth: 84, textAlign: 'center', color: '#fff', background: MODE_COLOR[mode] ?? '#8c8c8c', border: 'none' }}>
                      {MODE_LABEL[mode] ?? mode}
                    </Tag>
                    <span style={{ color: '#595959' }}>
                      {m.ranked.length === 0 ? '无结果' : m.ranked.map((id) => `#${id}`).join(' → ')}
                    </span>
                    <span style={{ marginLeft: 'auto', color: m.recall > 0 ? '#237804' : '#cf1322' }}>
                      R={m.recall.toFixed(2)}
                    </span>
                  </div>
                ))}
              </Card>
            ))}
          </Space>
        )}
      </Drawer>
    </div>
  )
}
