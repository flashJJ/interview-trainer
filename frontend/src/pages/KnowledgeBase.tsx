import { useState } from 'react'
import { App as AntdApp, Button, Card, Popconfirm, Space, Table, Tag, Typography } from 'antd'
import { FileTextOutlined, PlusOutlined, ReloadOutlined, RobotOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type {
  KnowledgeEntry,
  KnowledgeEntryDetail,
  RetrievalMode,
  SearchResultItem,
} from '@/api/types'
import { knowledgeApi } from '@/api/knowledge'
import {
  useKnowledgeEntries,
  useKnowledgeMutations,
  useKnowledgeStats,
} from '@/hooks/useKnowledge'
import { useQuestionMutations } from '@/hooks/useQuestions'
import KnowledgeStats from '@/components/knowledge/KnowledgeStats'
import SemanticSearchCard from '@/components/knowledge/SemanticSearchCard'
import CreateEntryModal, {
  type TextForm,
  type UploadForm,
  type UrlForm,
} from '@/components/knowledge/CreateEntryModal'
import EntryDetailDrawer from '@/components/knowledge/EntryDetailDrawer'
import GenerateQuestionsModal, {
  type GenForm,
} from '@/components/knowledge/GenerateQuestionsModal'
import { EntryStatusTag } from '@/components/common/StatusTags'
import { fmtTime, SOURCE_TYPE_TEXT } from '@/utils/constants'
import { stickyTableConfig } from '@/utils/stickyTable'

export default function KnowledgeBase() {
  const { message } = AntdApp.useApp()

  // 分页（客户端状态）
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(10)

  // 数据层：TanStack Query
  const { data: stats, refetch: refetchStats } = useKnowledgeStats()
  const {
    data: entryData,
    isLoading: loading,
    refetch: refetchEntries,
  } = useKnowledgeEntries({ page, size })
  const knowledgeMutations = useKnowledgeMutations()
  const { generate } = useQuestionMutations()
  const rows = entryData?.items ?? []
  const total = entryData?.total ?? 0

  // 交互状态（弹窗/抽屉/检索）
  const [createOpen, setCreateOpen] = useState(false)
  const [createLoading, setCreateLoading] = useState(false)
  const [detail, setDetail] = useState<KnowledgeEntryDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [searchResults, setSearchResults] = useState<SearchResultItem[] | null>(null)
  const [searchMeta, setSearchMeta] = useState<{ mode: string; elapsed_ms: number } | null>(null)
  const [searching, setSearching] = useState(false)
  const [genTarget, setGenTarget] = useState<KnowledgeEntry | null>(null)
  const [genLoading, setGenLoading] = useState(false)

  const onCreateText = async (values: TextForm) => {
    setCreateLoading(true)
    try {
      await knowledgeMutations.create.mutateAsync({
        title: values.title?.trim() ?? '',
        content: values.content.trim(),
      })
      message.success('录入成功，已开始处理')
      setCreateOpen(false)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '创建失败')
    } finally {
      setCreateLoading(false)
    }
  }

  const onCreateUpload = async (file: File, values: UploadForm) => {
    if (!/\.(txt|md|pdf|docx)$/i.test(file.name)) {
      message.error('仅支持 .txt / .md / .pdf / .docx 文件')
      return
    }
    setCreateLoading(true)
    try {
      await knowledgeMutations.upload.mutateAsync({ file, title: values.title?.trim() })
      message.success('上传成功，已开始处理')
      setCreateOpen(false)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '上传失败')
    } finally {
      setCreateLoading(false)
    }
  }

  const onCreateUrl = async (values: UrlForm) => {
    setCreateLoading(true)
    try {
      await knowledgeMutations.createFromUrl.mutateAsync({
        url: values.url.trim(),
        title: values.title?.trim(),
      })
      message.success('链接抓取成功，已开始处理')
      setCreateOpen(false)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '链接录入失败')
    } finally {
      setCreateLoading(false)
    }
  }

  const onReprocess = async (id: number) => {
    try {
      await knowledgeMutations.reprocess.mutateAsync(id)
      message.success('已触发重新处理')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  const onDelete = async (id: number) => {
    try {
      await knowledgeMutations.remove.mutateAsync(id)
      message.success('删除成功')
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

  const onSearch = async (query: string, mode: RetrievalMode = 'hybrid') => {
    if (!query) {
      message.warning('请输入检索内容')
      return
    }
    setSearching(true)
    try {
      const data = await knowledgeApi.search(query, 5, mode)
      setSearchResults(data.results)
      setSearchMeta({ mode: data.mode, elapsed_ms: data.elapsed_ms })
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
      const resp = await generate.mutateAsync({
        entry_id: genTarget.id,
        types: values.types,
        count_per_type: Number(values.count_per_type),
        difficulty: values.difficulty,
      })
      message.success(
        `已生成 ${resp.created_count} 道题（${resp.mode === 'llm' ? 'AI 生成' : '规则生成'}）`,
      )
      setGenTarget(null)
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
        <Tag icon={t === 'file' ? <FileTextOutlined /> : undefined}>{SOURCE_TYPE_TEXT[t]}</Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (s: KnowledgeEntry['status']) => <EntryStatusTag status={s} />,
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
            onClick={() => setGenTarget(record)}
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
      <KnowledgeStats stats={stats ?? null} />

      <SemanticSearchCard
        results={searchResults}
        loading={searching}
        onSearch={onSearch}
        meta={searchMeta}
      />

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
          sticky={stickyTableConfig}
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

      <CreateEntryModal
        open={createOpen}
        loading={createLoading}
        onClose={() => setCreateOpen(false)}
        onCreateText={onCreateText}
        onCreateUpload={onCreateUpload}
        onCreateUrl={onCreateUrl}
      />

      <EntryDetailDrawer
        detail={detail}
        loading={detailLoading}
        onClose={() => setDetail(null)}
      />

      <GenerateQuestionsModal
        key={genTarget?.id ?? 'closed'}
        entry={genTarget}
        loading={genLoading}
        onClose={() => setGenTarget(null)}
        onSubmit={onGenerate}
      />

      <div style={{ marginTop: 16, textAlign: 'right' }}>
        <Button
          icon={<ReloadOutlined />}
          onClick={() => {
            void refetchEntries()
            void refetchStats()
          }}
        >
          刷新
        </Button>
      </div>
    </div>
  )
}
