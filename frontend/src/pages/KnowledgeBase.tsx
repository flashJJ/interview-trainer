import { useCallback, useEffect, useState } from 'react'
import { Alert, Badge, Button, Card, Col, Descriptions, Drawer, Form, Input, List, Modal, Popconfirm, Row, Select, Space, Statistic, Table, Tabs, Tag, Typography, Upload } from 'antd'
import { App as AntdApp } from 'antd'
import {
  BookOutlined,
  FileTextOutlined,
  PlusOutlined,
  ReloadOutlined,
  RobotOutlined,
  SearchOutlined,
  UploadOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { knowledgeApi, questionApi } from '../api/client'
import type {
  Difficulty,
  KnowledgeChunk,
  KnowledgeEntry,
  KnowledgeOverview,
  QType,
  SearchResultItem,
} from '../api/types'
import {
  DIFFICULTIES,
  DIFFICULTY_TEXT,
  ENTRY_STATUS_COLOR,
  ENTRY_STATUS_TEXT,
  fmtTime,
  pct,
  QTYPES,
  Q_TYPE_TEXT,
  SOURCE_TYPE_TEXT,
} from '../utils/constants'

interface TextForm {
  title?: string
  content: string
}

interface UploadForm {
  title?: string
}

interface GenForm {
  types: QType[]
  count_per_type: number
  difficulty?: Difficulty
}

export default function KnowledgeBase() {
  const { message } = AntdApp.useApp()
  const [stats, setStats] = useState<KnowledgeOverview | null>(null)
  const [rows, setRows] = useState<KnowledgeEntry[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(10)
  const [loading, setLoading] = useState(false)

  const [createOpen, setCreateOpen] = useState(false)
  const [createLoading, setCreateLoading] = useState(false)
  const [uploadFile, setUploadFile] = useState<File | null>(null)

  const [detail, setDetail] = useState<{ entry: KnowledgeEntry; chunks: KnowledgeChunk[] } | null>(
    null,
  )
  const [detailLoading, setDetailLoading] = useState(false)

  const [searchQuery, setSearchQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [searchResults, setSearchResults] = useState<SearchResultItem[] | null>(null)

  const [genTarget, setGenTarget] = useState<KnowledgeEntry | null>(null)
  const [genLoading, setGenLoading] = useState(false)

  const [textForm] = Form.useForm<TextForm>()
  const [uploadForm] = Form.useForm<UploadForm>()
  const [genForm] = Form.useForm<GenForm>()

  const loadOverview = useCallback(async () => {
    try {
      const data = await knowledgeApi.overview()
      setStats(data)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '获取统计失败')
    }
  }, [])

  const loadList = useCallback(async () => {
    setLoading(true)
    try {
      const data = await knowledgeApi.listEntries({ page, size })
      setRows(data.items)
      setTotal(data.total)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '获取列表失败')
    } finally {
      setLoading(false)
    }
  }, [page, size])

  useEffect(() => {
    void loadOverview()
  }, [loadOverview])

  useEffect(() => {
    void loadList()
  }, [loadList])

  const onCreateText = async (values: TextForm) => {
    setCreateLoading(true)
    try {
      await knowledgeApi.createEntry(values.title?.trim() ?? '', values.content.trim())
      message.success('录入成功，已开始处理')
      setCreateOpen(false)
      textForm.resetFields()
      void loadList()
      void loadOverview()
    } catch (err) {
      message.error(err instanceof Error ? err.message : '创建失败')
    } finally {
      setCreateLoading(false)
    }
  }

  const onCreateUpload = async (values: UploadForm) => {
    if (!uploadFile) {
      message.error('请选择文件')
      return
    }
    if (!/\.(txt|md)$/i.test(uploadFile.name)) {
      message.error('仅支持 .txt / .md 文件')
      return
    }
    setCreateLoading(true)
    try {
      await knowledgeApi.uploadEntry(uploadFile, values.title?.trim())
      message.success('上传成功，已开始处理')
      setCreateOpen(false)
      uploadForm.resetFields()
      setUploadFile(null)
      void loadList()
      void loadOverview()
    } catch (err) {
      message.error(err instanceof Error ? err.message : '上传失败')
    } finally {
      setCreateLoading(false)
    }
  }

  const onReprocess = async (id: number) => {
    try {
      await knowledgeApi.reprocess(id)
      message.success('已触发重新处理')
      void loadList()
      void loadOverview()
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  const onDelete = async (id: number) => {
    try {
      await knowledgeApi.deleteEntry(id)
      message.success('删除成功')
      void loadList()
      void loadOverview()
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败')
    }
  }

  const onShowDetail = async (id: number) => {
    setDetailLoading(true)
    setDetail(null)
    try {
      const data = await knowledgeApi.getEntry(id)
      setDetail({ entry: data.entry, chunks: data.chunks })
    } catch (err) {
      message.error(err instanceof Error ? err.message : '获取详情失败')
    } finally {
      setDetailLoading(false)
    }
  }

  const onSearch = async () => {
    const q = searchQuery.trim()
    if (!q) {
      message.warning('请输入检索内容')
      return
    }
    setSearching(true)
    try {
      const data = await knowledgeApi.search(q, 5)
      setSearchResults(data.results)
      if (data.results.length === 0) message.info('未检索到相关内容')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '检索失败')
      setSearchResults(null)
    } finally {
      setSearching(false)
    }
  }

  const onGenerate = async (values: GenForm) => {
    if (!genTarget) return
    if (values.types.length === 0) {
      message.warning('请至少选择一种题型')
      return
    }
    setGenLoading(true)
    try {
      const resp = await questionApi.generate({
        entry_id: genTarget.id,
        types: values.types,
        count_per_type: values.count_per_type,
        difficulty: values.difficulty,
      })
      message.success(
        `已生成 ${resp.created_count} 道题（${resp.mode === 'llm' ? 'AI 生成' : '规则生成'}）`,
      )
      setGenTarget(null)
      void loadList()
    } catch (err) {
      message.error(err instanceof Error ? err.message : '生成失败')
    } finally {
      setGenLoading(false)
    }
  }

  const columns: ColumnsType<KnowledgeEntry> = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: { showTitle: false },
      render: (title: string) => (
        <Typography.Text strong style={{ maxWidth: 220 }} ellipsis>
          {title}
        </Typography.Text>
      ),
    },
    {
      title: '来源',
      dataIndex: 'source_type',
      key: 'source_type',
      width: 80,
      render: (t: KnowledgeEntry['source_type']) => (
        <Tag icon={t === 'file' ? <FileTextOutlined /> : undefined}>
          {SOURCE_TYPE_TEXT[t]}
        </Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (s: KnowledgeEntry['status']) => (
        <Tag color={ENTRY_STATUS_COLOR[s]}>{ENTRY_STATUS_TEXT[s]}</Tag>
      ),
    },
    { title: '块数', dataIndex: 'chunk_count', key: 'chunk_count', width: 70 },
    { title: '题目数', dataIndex: 'question_count', key: 'question_count', width: 80 },
    { title: '字数', dataIndex: 'char_count', key: 'char_count', width: 80 },
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
      width: 260,
      fixed: 'right',
      render: (_, record) => (
        <Space size={4} wrap>
          <Button type="link" size="small" onClick={() => void onShowDetail(record.id)}>
            详情
          </Button>
          <Button type="link" size="small" onClick={() => void onReprocess(record.id)}>
            重新处理
          </Button>
          <Button
            type="link"
            size="small"
            icon={<RobotOutlined />}
            onClick={() => {
              genForm.setFieldsValue({
                types: [...QTYPES],
                count_per_type: 3,
                difficulty: undefined,
              })
              setGenTarget(record)
            }}
          >
            AI 出题
          </Button>
          <Popconfirm
            title="确认删除"
            description="删除后其分块、题目与向量将一并删除，不可恢复。"
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

      <Card
        title="语义检索"
        size="small"
        style={{ marginBottom: 16 }}
        extra={
          <Space>
            <Input
              placeholder="输入要检索的内容，如：缓存穿透怎么解决"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onPressEnter={() => void onSearch()}
              style={{ width: 320 }}
              allowClear
            />
            <Button
              type="primary"
              icon={<SearchOutlined />}
              loading={searching}
              onClick={() => void onSearch()}
            >
              检索
            </Button>
          </Space>
        }
      >
        {searchResults === null ? (
          <Typography.Text type="secondary">
            基于向量语义的检索将返回最相关的知识块（Top 5），可查看来源资料、相似度与内容摘要。
          </Typography.Text>
        ) : searchResults.length === 0 ? (
          <Typography.Text type="secondary">暂无检索结果，请尝试其他关键词。</Typography.Text>
        ) : (
          <List
            dataSource={searchResults}
            renderItem={(item) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <Space size={8}>
                      <Tag color="blue">{item.entry_title}</Tag>
                      <Typography.Text type="secondary">块 #{item.seq + 1}</Typography.Text>
                      <Badge
                        count={`相似度 ${pct(item.score)}`}
                        style={{ backgroundColor: '#52c41a' }}
                      />
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
        )}
      </Card>

      <Card
        title="知识库管理"
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            新建知识库
          </Button>
        }
      >
        <Table<KnowledgeEntry>
          rowKey="id"
          columns={columns}
          dataSource={rows}
          loading={loading}
          scroll={{ x: 1200 }}
          pagination={{
            current: page,
            pageSize: size,
            total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p, s) => {
              setPage(p)
              setSize(s)
            },
          }}
        />
      </Card>

      <Modal
        title="新建知识库"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        afterClose={() => setUploadFile(null)}
        footer={null}
        width={640}
        destroyOnHidden
      >
        <Tabs
          destroyInactiveTabPane
          items={[
            {
              key: 'text',
              label: '文本录入',
              children: (
                <Form<TextForm> layout="vertical" form={textForm} onFinish={onCreateText}>
                  <Form.Item name="title" label="标题（可选，缺省取正文首行前 30 字）">
                    <Input placeholder="请输入标题" maxLength={100} />
                  </Form.Item>
                  <Form.Item
                    name="content"
                    label="正文内容"
                    rules={[{ required: true, message: '请输入正文内容' }]}
                  >
                      <Input.TextArea
                        rows={10}
                        placeholder="请粘贴技术笔记、文档或源码片段…"
                        showCount
                        maxLength={100000}
                      />
                  </Form.Item>
                  <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
                    <Space>
                      <Button onClick={() => setCreateOpen(false)}>取消</Button>
                      <Button type="primary" htmlType="submit" loading={createLoading}>
                        提交录入
                      </Button>
                    </Space>
                  </Form.Item>
                </Form>
              ),
            },
            {
              key: 'file',
              label: '文件上传',
              children: (
                <Form<UploadForm> layout="vertical" form={uploadForm} onFinish={onCreateUpload}>
                  <Alert
                    type="info"
                    showIcon
                    message="仅支持 .txt / .md 文件（UTF-8 编码），大小不超过 5MB"
                    style={{ marginBottom: 16 }}
                  />
                  <Form.Item name="title" label="标题（可选，缺省自动识别）">
                    <Input placeholder="请输入标题" maxLength={100} />
                  </Form.Item>
                  <Form.Item label="选择文件" required>
                    <Upload
                      accept=".txt,.md"
                      maxCount={1}
                      beforeUpload={(file) => {
                        setUploadFile(file)
                        return false
                      }}
                      onRemove={() => setUploadFile(null)}
                    >
                      <Button icon={<UploadOutlined />}>选择 .txt / .md 文件</Button>
                    </Upload>
                  </Form.Item>
                  <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
                    <Space>
                      <Button onClick={() => setCreateOpen(false)}>取消</Button>
                      <Button type="primary" htmlType="submit" loading={createLoading}>
                        上传并处理
                      </Button>
                    </Space>
                  </Form.Item>
                </Form>
              ),
            },
          ]}
        />
      </Modal>

      <Drawer
        title="知识库详情"
        width={720}
        open={detail !== null}
        onClose={() => setDetail(null)}
        loading={detailLoading}
      >
        {detail && (
          <>
            <Descriptions column={2} size="small" style={{ marginBottom: 16 }}>
              <Descriptions.Item label="标题">{detail.entry.title}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={ENTRY_STATUS_COLOR[detail.entry.status]}>
                  {ENTRY_STATUS_TEXT[detail.entry.status]}
                </Tag>
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
                    title={<Space size={8}><Badge count={chunk.seq + 1} color="#2f54eb" /><Typography.Text type="secondary">{chunk.char_count} 字</Typography.Text></Space>}
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

      <Modal
        title={`AI 出题 - ${genTarget?.title ?? ''}`}
        open={genTarget !== null}
        onCancel={() => setGenTarget(null)}
        footer={null}
        destroyOnHidden
      >
        <Form<GenForm>
          layout="vertical"
          form={genForm}
          initialValues={{ types: [...QTYPES], count_per_type: 3 }}
          onFinish={onGenerate}
        >
          <Form.Item
            name="types"
            label="题型（多选）"
            rules={[{ required: true, message: '请至少选择一种题型' }]}
          >
            <Select mode="multiple" placeholder="请选择题型" options={QTYPES.map((t) => ({ label: Q_TYPE_TEXT[t], value: t }))} />
          </Form.Item>
          <Form.Item
            name="count_per_type"
            label="每题型数量"
            rules={[{ required: true, message: '请输入数量' }]}
          >
            <Input type="number" min={1} max={10} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="difficulty" label="难度（可选）">
            <Select
              placeholder="不限"
              allowClear
              options={DIFFICULTIES.map((d) => ({ label: DIFFICULTY_TEXT[d], value: d }))}
            />
          </Form.Item>
          <Alert
            type="info"
            showIcon
            message="未配置 LLM API Key 时将使用内置规则引擎生成题目，质量以 UI 徽标为准。"
            style={{ marginBottom: 16 }}
          />
          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button onClick={() => setGenTarget(null)}>取消</Button>
              <Button type="primary" htmlType="submit" icon={<RobotOutlined />} loading={genLoading}>
                开始生成
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      <div style={{ marginTop: 16, textAlign: 'right' }}>
        <Button icon={<ReloadOutlined />} onClick={() => { void loadList(); void loadOverview() }}>
          刷新
        </Button>
      </div>
    </div>
  )
}
