import { useCallback, useEffect, useState } from 'react'
import { Button, Card, Descriptions, Form, Input, Modal, Popconfirm, Select, Space, Table, Tag, Typography } from 'antd'
import { App as AntdApp } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { questionApi } from '../api/client'
import type { Difficulty, PageResp, QType, Question } from '../api/types'
import {
  DIFFICULTIES,
  DIFFICULTY_COLOR,
  DIFFICULTY_TEXT,
  fmtTime,
  QUESTION_SOURCE_TEXT,
  QTYPES,
  Q_TYPE_COLOR,
  Q_TYPE_TEXT,
  truncate,
} from '../utils/constants'

interface FilterForm {
  q_type?: QType
  difficulty?: Difficulty
  keyword?: string
}

export default function QuestionBank() {
  const { message } = AntdApp.useApp()
  const [rows, setRows] = useState<Question[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(10)
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState<FilterForm>({})

  const [detail, setDetail] = useState<Question | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const [form] = Form.useForm<FilterForm>()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data: PageResp<Question> = await questionApi.list({
        page,
        size,
        q_type: filters.q_type,
        difficulty: filters.difficulty,
        keyword: filters.keyword?.trim() || undefined,
      })
      setRows(data.items)
      setTotal(data.total)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '获取题库列表失败')
    } finally {
      setLoading(false)
    }
  }, [page, size, filters])

  useEffect(() => {
    void load()
  }, [load])

  const onSearch = (values: FilterForm) => {
    setPage(1)
    setFilters(values)
  }

  const onReset = () => {
    form.resetFields()
    setPage(1)
    setFilters({})
  }

  const onShowDetail = async (id: number) => {
    setDetailLoading(true)
    setDetail(null)
    try {
      const data = await questionApi.get(id)
      setDetail(data)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '获取题目详情失败')
    } finally {
      setDetailLoading(false)
    }
  }

  const onDelete = async (id: number) => {
    try {
      await questionApi.remove(id)
      message.success('删除成功')
      void load()
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败')
    }
  }

  const columns: ColumnsType<Question> = [
    {
      title: '内容',
      dataIndex: 'content',
      key: 'content',
      ellipsis: { showTitle: false },
      render: (content: string) => (
        <Typography.Text style={{ maxWidth: 360 }} ellipsis>
          {truncate(content, 60)}
        </Typography.Text>
      ),
    },
    {
      title: '题型',
      dataIndex: 'q_type',
      key: 'q_type',
      width: 90,
      render: (t: QType) => <Tag color={Q_TYPE_COLOR[t]}>{Q_TYPE_TEXT[t]}</Tag>,
    },
    {
      title: '难度',
      dataIndex: 'difficulty',
      key: 'difficulty',
      width: 80,
      render: (d: Difficulty) => <Tag color={DIFFICULTY_COLOR[d]}>{DIFFICULTY_TEXT[d]}</Tag>,
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 100,
      render: (s: Question['source']) => (
        <Tag color={s === 'llm' ? 'magenta' : 'default'}>{QUESTION_SOURCE_TEXT[s]}</Tag>
      ),
    },
    {
      title: '所属资料',
      dataIndex: 'entry_title',
      key: 'entry_title',
      width: 180,
      ellipsis: true,
      render: (t: string | null) => t ?? <Typography.Text type="secondary">-</Typography.Text>,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: fmtTime,
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      fixed: 'right',
      render: (_, record) => (
        <Space size={4}>
          <Button type="link" size="small" onClick={() => void onShowDetail(record.id)}>
            详情
          </Button>
          <Popconfirm
            title="确认删除"
            description="删除后该题目不可恢复。"
            okText="删除"
            okButtonProps={{ danger: true }}
            cancelText="取消"
            onConfirm={() => void onDelete(record.id)}
          >
            <Button type="link" size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Form form={form} layout="inline" onFinish={onSearch} initialValues={{}}>
          <Form.Item name="q_type" label="题型">
            <Select
              placeholder="全部题型"
              allowClear
              style={{ width: 140 }}
              options={QTYPES.map((t) => ({ label: Q_TYPE_TEXT[t], value: t }))}
            />
          </Form.Item>
          <Form.Item name="difficulty" label="难度">
            <Select
              placeholder="全部难度"
              allowClear
              style={{ width: 140 }}
              options={DIFFICULTIES.map((d) => ({ label: DIFFICULTY_TEXT[d], value: d }))}
            />
          </Form.Item>
          <Form.Item name="keyword" label="关键词">
            <Input
              placeholder="题目内容关键词"
              allowClear
              style={{ width: 220 }}
              onPressEnter={() => form.submit()}
            />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" icon={<SearchOutlined />}>
                搜索
              </Button>
              <Button onClick={onReset}>重置</Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>

      <Card title="题库">
        <Table<Question>
          rowKey="id"
          columns={columns}
          dataSource={rows}
          loading={loading}
          scroll={{ x: 1100 }}
          pagination={{
            current: page,
            pageSize: size,
            total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (t) => `共 ${t} 题`,
            onChange: (p, s) => {
              setPage(p)
              setSize(s)
            },
          }}
        />
      </Card>

      <Modal
        title="题目详情"
        open={detail !== null}
        onCancel={() => setDetail(null)}
        footer={
          <Button onClick={() => setDetail(null)}>关闭</Button>
        }
        width={680}
      >
        {detailLoading && <Typography.Text type="secondary">加载中…</Typography.Text>}
        {detail && (
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="题型">
              <Tag color={Q_TYPE_COLOR[detail.q_type]}>{Q_TYPE_TEXT[detail.q_type]}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="难度">
              <Tag color={DIFFICULTY_COLOR[detail.difficulty]}>{DIFFICULTY_TEXT[detail.difficulty]}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="来源">
              <Tag color={detail.source === 'llm' ? 'magenta' : 'default'}>
                {QUESTION_SOURCE_TEXT[detail.source]}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="所属资料">
              {detail.entry_title ?? '-'}
            </Descriptions.Item>
            <Descriptions.Item label="题目内容">
              <Typography.Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>
                {detail.content}
              </Typography.Paragraph>
            </Descriptions.Item>
            {detail.options && detail.options.length > 0 && (
              <Descriptions.Item label="选项">
                <Space direction="vertical" size={4}>
                  {detail.options.map((opt) => (
                    <Typography.Text key={opt}>{opt}</Typography.Text>
                  ))}
                </Space>
              </Descriptions.Item>
            )}
            <Descriptions.Item label="标准答案">
              <Typography.Text strong>{detail.answer}</Typography.Text>
            </Descriptions.Item>
            <Descriptions.Item label="解析">
              <Typography.Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>
                {detail.explanation || '-'}
              </Typography.Paragraph>
            </Descriptions.Item>
            <Descriptions.Item label="关键词">
              <Space size={4} wrap>
                {detail.keywords.length > 0 ? (
                  detail.keywords.map((kw) => (
                    <Tag key={kw} color="geekblue">
                      {kw}
                    </Tag>
                  ))
                ) : (
                  <Typography.Text type="secondary">暂无</Typography.Text>
                )}
              </Space>
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">{fmtTime(detail.created_at)}</Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  )
}
