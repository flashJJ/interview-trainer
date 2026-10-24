import { useState } from 'react'
import {
  Alert,
  App as AntdApp,
  Button,
  Card,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from 'antd'
import { AuditOutlined, CheckOutlined, CloseOutlined, EditOutlined } from '@ant-design/icons'
import { useQuestionMutations, useQuestions } from '@/hooks/useQuestions'
import type { Difficulty, QType, Question } from '../api/types'
import { DIFFICULTY_TEXT, Q_TYPE_COLOR, Q_TYPE_TEXT } from '../utils/constants'

interface EditFormValues {
  content: string
  options: string[]
  answer: string
  explanation: string
  difficulty: Difficulty
}

export default function Review() {
  const { message } = AntdApp.useApp()
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(10)
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [editing, setEditing] = useState<Question | null>(null)
  const [form] = Form.useForm<EditFormValues>()

  // 数据层：TanStack Query 统一管理（待审核队列）
  const { data: pendingData, isLoading: loading } = useQuestions({
    page,
    size,
    review_status: 'pending',
  })
  const { review, batchReview, update } = useQuestionMutations()
  const items = pendingData?.items ?? []
  const total = pendingData?.total ?? 0
  const submitting = update.isPending || review.isPending

  const onReview = async (id: number, action: 'approve' | 'reject') => {
    try {
      await review.mutateAsync({ id, action })
      message.success(action === 'approve' ? '已通过，进入组卷池' : '已拒绝')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  const onBatch = async (action: 'approve' | 'reject') => {
    if (selectedIds.length === 0) return
    try {
      const result = await batchReview.mutateAsync({ ids: selectedIds, action })
      message.success(result.message)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '批量操作失败')
    }
  }

  const openEditor = (question: Question) => {
    setEditing(question)
    form.setFieldsValue({
      content: question.content,
      options: question.options ?? [],
      answer: question.answer,
      explanation: question.explanation,
      difficulty: question.difficulty,
    })
  }

  const onEditSubmit = async (values: EditFormValues) => {
    if (!editing) return
    try {
      await update.mutateAsync({ id: editing.id, payload: {
        content: values.content,
        options: editing.q_type === 'choice' ? values.options : undefined,
        answer: values.answer,
        explanation: values.explanation,
        difficulty: values.difficulty,
      } })
      // 编辑后直接通过审核
      await review.mutateAsync({ id: editing.id, action: 'approve' })
      message.success('已保存并通过审核')
      setEditing(null)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '保存失败')
    }
  }

  const columns = [
    {
      title: '题目',
      dataIndex: 'content',
      key: 'content',
      ellipsis: true,
      render: (text: string) => (
        <Typography.Text ellipsis style={{ maxWidth: 360 }}>
          {text}
        </Typography.Text>
      ),
    },
    {
      title: '题型',
      dataIndex: 'q_type',
      key: 'q_type',
      width: 80,
      render: (t: QType) => <Tag color={Q_TYPE_COLOR[t]}>{Q_TYPE_TEXT[t]}</Tag>,
    },
    {
      title: '难度',
      dataIndex: 'difficulty',
      key: 'difficulty',
      width: 80,
      render: (d: Difficulty) => DIFFICULTY_TEXT[d],
    },
    {
      title: '来源资料',
      dataIndex: 'entry_title',
      key: 'entry_title',
      width: 150,
      ellipsis: true,
      render: (t: string | null) => t ?? <Typography.Text type="secondary">—</Typography.Text>,
    },
    {
      title: '生成方式',
      dataIndex: 'source',
      key: 'source',
      width: 100,
      render: (s: string) => (
        <Tag color={s === 'llm' ? 'magenta' : 'default'}>{s === 'llm' ? 'AI 生成' : '规则生成'}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: unknown, record: Question) => (
        <Space size={4}>
          <Button
            type="link"
            size="small"
            icon={<CheckOutlined />}
            onClick={() => void onReview(record.id, 'approve')}
          >
            通过
          </Button>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEditor(record)}
          >
            编辑后通过
          </Button>
          <Popconfirm
            title="拒绝该题"
            description="拒绝后题目不进入组卷池，确定吗？"
            onConfirm={() => void onReview(record.id, 'reject')}
            okText="拒绝"
            cancelText="取消"
          >
            <Button type="link" size="small" danger icon={<CloseOutlined />}>
              拒绝
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Typography.Title level={4}>
        <AuditOutlined style={{ marginRight: 8 }} />
        题目审核
      </Typography.Title>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="AI 生成的题目先进入待审核队列"
        description="审核通过的题目才会进入组卷池；可以逐题通过/拒绝，也可以编辑修正后通过，或按资料批量通过。被考卷引用的题目不可删除。"
      />

      <Card style={{ marginBottom: 16 }}>
        <Space size={48} wrap style={{ width: '100%', justifyContent: 'space-between' }}>
          <Statistic title="待审核题目" value={total} valueStyle={{ color: '#fa8c16' }} />
          <Space>
            <Button
              type="primary"
              icon={<CheckOutlined />}
              disabled={selectedIds.length === 0}
              onClick={() => void onBatch('approve')}
            >
              批量通过（{selectedIds.length}）
            </Button>
            <Button
              danger
              icon={<CloseOutlined />}
              disabled={selectedIds.length === 0}
              onClick={() => void onBatch('reject')}
            >
              批量拒绝（{selectedIds.length}）
            </Button>
          </Space>
        </Space>
      </Card>

      <Card>
        <Table<Question>
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={items}
          rowSelection={{
            selectedRowKeys: selectedIds,
            onChange: (keys) => setSelectedIds(keys as number[]),
          }}
          pagination={{
            current: page,
            pageSize: size,
            total,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 题待审`,
            onChange: (p, s) => {
              setPage(p)
              setSize(s)
            },
          }}
        />
      </Card>

      <Modal
        title="编辑题目（保存后自动通过审核）"
        open={editing !== null}
        onCancel={() => setEditing(null)}
        onOk={() => void form.submit()}
        confirmLoading={submitting}
        okText="保存并通过"
        cancelText="取消"
        width={640}
        forceRender
      >
        <Form<EditFormValues>
            form={form}
            layout="vertical"
            onFinish={onEditSubmit}
            requiredMark={false}
            style={{ marginTop: 16 }}
          >
            <Form.Item
              name="content"
              label="题干"
              rules={[{ required: true, message: '请输入题干' }]}
              extra={
                editing?.q_type === 'fill'
                  ? '填空题题干需包含 ______ 空位'
                  : editing?.q_type === 'judge'
                    ? '判断题题干为完整陈述'
                    : undefined
              }
            >
              <Input.TextArea rows={3} />
            </Form.Item>

            {editing?.q_type === 'choice' && (
              <Form.Item label="选项（A/B/C/D）" required>
                <Space direction="vertical" style={{ width: '100%' }}>
                  {[0, 1, 2, 3].map((i) => (
                    <Form.Item
                      key={i}
                      name={['options', i]}
                      noStyle
                      rules={[{ required: true, message: `选项 ${'ABCD'[i]} 不能为空` }]}
                    >
                      <Input addonBefore={'ABCD'[i]} placeholder={`选项 ${'ABCD'[i]}`} />
                    </Form.Item>
                  ))}
                </Space>
              </Form.Item>
            )}

            <Form.Item
              name="answer"
              label="标准答案"
              rules={[{ required: true, message: '请输入标准答案' }]}
            >
              {editing?.q_type === 'choice' ? (
                <Select
                  options={[
                    { value: 'A', label: 'A' },
                    { value: 'B', label: 'B' },
                    { value: 'C', label: 'C' },
                    { value: 'D', label: 'D' },
                  ]}
                />
              ) : editing?.q_type === 'judge' ? (
                <Select
                  options={[
                    { value: '正确', label: '正确' },
                    { value: '错误', label: '错误' },
                  ]}
                />
              ) : (
                <Input placeholder="标准答案（多个等价答案用 / 分隔）" />
              )}
            </Form.Item>

            <Form.Item name="explanation" label="解析">
              <Input.TextArea rows={3} placeholder="答案解析" />
            </Form.Item>

            <Form.Item name="difficulty" label="难度">
              <Select
                options={[
                  { value: 'easy', label: '简单' },
                  { value: 'medium', label: '中等' },
                  { value: 'hard', label: '困难' },
                ]}
              />
            </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
