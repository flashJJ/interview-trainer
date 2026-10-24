import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  App as AntdApp,
  Button,
  Card,
  Popconfirm,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from 'antd'
import { CarryOutOutlined, ReloadOutlined, RobotOutlined, ThunderboltOutlined } from '@ant-design/icons'
import AITutorDrawer from '../components/AITutorDrawer'
import { wrongQuestionsApi } from '../api/client'
import type { Difficulty, QType, WrongQuestionItem } from '../api/types'
import { DIFFICULTY_COLOR, DIFFICULTY_TEXT, Q_TYPE_COLOR, Q_TYPE_TEXT } from '../utils/constants'

export default function WrongQuestions() {
  const [tutorOpen, setTutorOpen] = useState(false)
  const [tutorQuestionId, setTutorQuestionId] = useState<number | null>(null)
  const [tutorTitle, setTutorTitle] = useState('')

  const { message } = AntdApp.useApp()
  const navigate = useNavigate()

  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState<{
    total: number
    due_today: number
    overdue: number
    due_next_7_days: number
  } | null>(null)
  const [items, setItems] = useState<WrongQuestionItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(10)
  const [qType, setQType] = useState<QType | ''>('')
  const [onlyDue, setOnlyDue] = useState(false)
  const [generating, setGenerating] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [statsResp, listResp] = await Promise.all([
        wrongQuestionsApi.stats(),
        wrongQuestionsApi.list({ page, size, q_type: qType, only_due: onlyDue }),
      ])
      setStats(statsResp)
      setItems(listResp.items)
      setTotal(listResp.total)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [page, size, qType, onlyDue, message])

  useEffect(() => {
    void load()
  }, [load])

  const onStartReview = async () => {
    setGenerating(true)
    try {
      const paper = await wrongQuestionsApi.generateReview(10)
      message.success(`复习卷已生成，共 ${paper.question_count} 题`)
      navigate(`/exam/${paper.id}`)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '生成复习卷失败')
    } finally {
      setGenerating(false)
    }
  }

  const dueTag = (item: WrongQuestionItem) => {
    if (item.days_until_due < 0) {
      return <Tag color="red">已逾期 {-item.days_until_due} 天</Tag>
    }
    if (item.days_until_due === 0) {
      return <Tag color="orange">今天待复习</Tag>
    }
    return <Tag color="default">{item.days_until_due} 天后</Tag>
  }

  const columns = [
    {
      title: '题目',
      dataIndex: 'content',
      key: 'content',
      ellipsis: true,
      render: (text: string) => (
        <Typography.Text ellipsis style={{ maxWidth: 380 }}>
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
      render: (d: Difficulty) => <Tag color={DIFFICULTY_COLOR[d]}>{DIFFICULTY_TEXT[d]}</Tag>,
    },
    {
      title: '来源',
      dataIndex: 'entry_title',
      key: 'entry_title',
      width: 160,
      ellipsis: true,
      render: (t: string | null) => t ?? <Typography.Text type="secondary">—</Typography.Text>,
    },
    {
      title: '错误次数',
      dataIndex: 'error_count',
      key: 'error_count',
      width: 90,
      sorter: (a: WrongQuestionItem, b: WrongQuestionItem) => a.error_count - b.error_count,
      render: (n: number) => (
        <Tag color={n >= 3 ? 'red' : n >= 2 ? 'orange' : 'blue'}>{n} 次</Tag>
      ),
    },
    {
      title: '复习排期',
      key: 'due',
      width: 130,
      render: (_: unknown, item: WrongQuestionItem) => (
        <Space size={4} wrap>
          {dueTag(item)}
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            间隔 {item.interval_days} 天 / 连对 {item.repetitions}
          </Typography.Text>
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_: unknown, item: WrongQuestionItem) => (
        <Space size={4}>
          <Button
            type="link"
            size="small"
            icon={<RobotOutlined />}
            onClick={() => {
              setTutorQuestionId(item.question_id)
              setTutorTitle(item.content)
              setTutorOpen(true)
            }}
          >
            问 AI
          </Button>
          <Popconfirm
            title="标记掌握"
            description="将该题移出错题本，确定吗？"
            onConfirm={async () => {
              await wrongQuestionsApi.master(item.id)
              message.success('已标记掌握')
              void load()
            }}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" size="small">
              标记掌握
            </Button>
          </Popconfirm>
          <Popconfirm
            title="移出错题本"
            description="移出后将不再安排该题复习，确定吗？"
            onConfirm={async () => {
              await wrongQuestionsApi.remove(item.id)
              message.success('已移出')
              void load()
            }}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" size="small" danger>
              移出
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const dueCount = (stats?.due_today ?? 0) + (stats?.overdue ?? 0)

  return (
    <div>
      <AITutorDrawer
        questionId={tutorQuestionId}
        questionTitle={tutorTitle}
        open={tutorOpen}
        onClose={() => setTutorOpen(false)}
      />
      <Typography.Title level={4}>
        <CarryOutOutlined style={{ marginRight: 8 }} />
        错题本
      </Typography.Title>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="基于 SM-2 间隔重复算法自动排期"
        description="考试中答错的题会自动收入错题本；复习答对后按 1 天 → 6 天 → 间隔×难易度 的节奏拉长复习周期，连续答对且间隔达标后自动移出（视为掌握）。也可以手动标记掌握。"
      />

      <Card style={{ marginBottom: 16 }}>
        <Space size={48} wrap style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space size={48} wrap>
            <Statistic
              title="错题总数"
              value={stats?.total ?? 0}
              valueStyle={{ color: '#cf1322' }}
            />
            <Statistic
              title="今日待复习"
              value={stats?.due_today ?? 0}
              valueStyle={{ color: '#fa8c16' }}
            />
            <Statistic
              title="已逾期"
              value={stats?.overdue ?? 0}
              valueStyle={{ color: '#cf1322' }}
            />
            <Statistic title="未来 7 天" value={stats?.due_next_7_days ?? 0} />
          </Space>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => void load()}>
              刷新
            </Button>
            <Button
              type="primary"
              size="large"
              icon={<ThunderboltOutlined />}
              loading={generating}
              disabled={dueCount === 0}
              onClick={() => void onStartReview()}
            >
              开始复习（{dueCount} 题到期）
            </Button>
          </Space>
        </Space>
      </Card>

      <Card>
        <Space style={{ marginBottom: 16 }} wrap>
          <Space>
            <span>题型：</span>
            <Space.Compact>
              <Button
                type={qType === '' ? 'primary' : 'default'}
                onClick={() => {
                  setQType('')
                  setPage(1)
                }}
              >
                全部
              </Button>
              <Button
                type={qType === 'choice' ? 'primary' : 'default'}
                onClick={() => {
                  setQType('choice')
                  setPage(1)
                }}
              >
                单选
              </Button>
              <Button
                type={qType === 'fill' ? 'primary' : 'default'}
                onClick={() => {
                  setQType('fill')
                  setPage(1)
                }}
              >
                填空
              </Button>
              <Button
                type={qType === 'judge' ? 'primary' : 'default'}
                onClick={() => {
                  setQType('judge')
                  setPage(1)
                }}
              >
                判断
              </Button>
            </Space.Compact>
          </Space>
          <Button
            type={onlyDue ? 'primary' : 'default'}
            onClick={() => {
              setOnlyDue(!onlyDue)
              setPage(1)
            }}
          >
            只看到期
          </Button>
        </Space>

        <Table<WrongQuestionItem>
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={items}
          pagination={{
            current: page,
            pageSize: size,
            total,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 题`,
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
