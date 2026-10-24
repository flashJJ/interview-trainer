import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Alert, Button, Card, Form, Input, InputNumber, Select, Space, Table, Tag, Typography } from 'antd'
import { App as AntdApp } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { useExamMutations, useExamPapers } from '@/hooks/useExams'
import type { Difficulty, ExamPaper, PageResp, QType } from '../api/types'
import {
  DIFFICULTIES,
  DIFFICULTY_TEXT,
  fmtTime,
  pct,
  QTYPES,
  Q_TYPE_TEXT,
} from '../utils/constants'

interface GenForm {
  title?: string
  count: number
  types: QType[]
  difficulty?: Difficulty
}

export default function Practice() {
  const { message } = AntdApp.useApp()
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(10)

  const [genForm] = Form.useForm<GenForm>()

  // 数据层：TanStack Query 统一管理
  const { data: paperData, isLoading: loading } = useExamPapers(page, size)
  const { generate } = useExamMutations()
  const rows = paperData?.items ?? []
  const total = paperData?.total ?? 0
  const genLoading = generate.isPending

  const onGenerate = async (values: GenForm) => {
    if (values.types.length === 0) {
      message.warning('请至少选择一种题型')
      return
    }
    try {
      const paper = await generate.mutateAsync({
        title: values.title?.trim() || undefined,
        count: values.count,
        types: values.types,
        difficulty: values.difficulty,
      })
      message.success(`考卷「${paper.title}」生成成功，共 ${paper.question_count} 题`)
      navigate(`/exam/${paper.id}`)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '生成考卷失败')
    }
  }

  const columns: ColumnsType<ExamPaper> = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      render: (title: string) => <Typography.Text strong>{title}</Typography.Text>,
    },
    { title: '题目数', dataIndex: 'question_count', key: 'question_count', width: 90 },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170, render: fmtTime },
    {
      title: '最近成绩',
      key: 'latest_session',
      width: 200,
      render: (_, record) => {
        const s = record.latest_session
        if (!s || s.status !== 'submitted' || s.max_score <= 0) {
          return <Typography.Text type="secondary">未考试</Typography.Text>
        }
        const rate = s.total_score / s.max_score
        return (
          <Space direction="vertical" size={0}>
            <Typography.Text strong>
              {s.total_score} / {s.max_score}
            </Typography.Text>
            <Tag color={rate >= 0.6 ? 'green' : 'red'}>{pct(rate)}</Tag>
          </Space>
        )
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 220,
      fixed: 'right',
      render: (_, record) => (
        <Space size={4}>
          <Button type="link" size="small" onClick={() => navigate(`/exam/${record.id}`)}>
            查看题目
          </Button>
          <Button type="primary" size="small" onClick={() => navigate(`/exam/${record.id}`)}>
            开始考试
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Card title="生成随机考卷" style={{ marginBottom: 16 }}>
        <Alert
          type="info"
          showIcon
          message="从题库中随机不重复抽取题目；库存不足时会给出明确提示，不会静默凑数。"
          style={{ marginBottom: 16 }}
        />
        <Form<GenForm>
          form={genForm}
          layout="vertical"
          style={{ maxWidth: 520 }}
          initialValues={{ count: 10, types: [...QTYPES] }}
          onFinish={onGenerate}
        >
          <Form.Item name="title" label="考卷标题（可选，缺省自动生成）">
            <Input placeholder="例如：Redis 专项练习" maxLength={100} />
          </Form.Item>
          <Form.Item
            name="count"
            label="题目数量"
            rules={[{ required: true, message: '请输入题目数量' }]}
          >
            <InputNumber min={1} max={100} style={{ width: '100%' }} />
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
          <Form.Item name="difficulty" label="难度（可选）">
            <Select
              placeholder="不限"
              allowClear
              options={DIFFICULTIES.map((d) => ({ label: DIFFICULTY_TEXT[d], value: d }))}
            />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Button type="primary" htmlType="submit" icon={<PlusOutlined />} loading={genLoading}>
              生成考卷并开始
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <Card title="我的考卷">
        <Table<ExamPaper>
          rowKey="id"
          columns={columns}
          dataSource={rows}
          loading={loading}
          scroll={{ x: 900 }}
          pagination={{
            current: page,
            pageSize: size,
            total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (t) => `共 ${t} 份`,
            onChange: (p, s) => {
              setPage(p)
              setSize(s)
            },
          }}
        />
      </Card>
    </div>
  )
}
