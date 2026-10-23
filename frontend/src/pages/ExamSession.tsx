import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Alert, Button, Card, Empty, Form, Input, Modal, Radio, Row, Space, Spin, Statistic, Tag, Typography } from 'antd'
import { App as AntdApp } from 'antd'
import { CheckCircleOutlined } from '@ant-design/icons'
import { examApi } from '../api/client'
import type { ExamQuestion } from '../api/types'
import {
  DIFFICULTY_COLOR,
  DIFFICULTY_TEXT,
  Q_TYPE_COLOR,
  Q_TYPE_TEXT,
} from '../utils/constants'

const JUDGE_OPTIONS = [
  { label: '正确', value: '正确' },
  { label: '错误', value: '错误' },
]

export default function ExamSession() {
  const { message } = AntdApp.useApp()
  const { paperId } = useParams<{ paperId: string }>()
  const navigate = useNavigate()

  const [loading, setLoading] = useState(true)
  const [paperTitle, setPaperTitle] = useState('在线考试')
  const [questions, setQuestions] = useState<ExamQuestion[]>([])
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [form] = Form.useForm<{ answers: Record<string, string> }>()

  const answers = Form.useWatch<Record<string, string>>('answers', form) ?? {}

  useEffect(() => {
    if (!paperId) return
    let cancelled = false
    setLoading(true)
    // 并行获取考卷标题与考试会话（重复进入会返回同一未提交会话，实现断点续考）
    Promise.all([examApi.start(Number(paperId)), examApi.getPaper(Number(paperId))])
      .then(([startResp, paperResp]) => {
        if (cancelled) return
        setQuestions(startResp.questions)
        setSessionId(startResp.session.id)
        setPaperTitle(paperResp.paper.title)
        const prefilled: Record<string, string> = {}
        for (const a of startResp.answers) {
          prefilled[String(a.question_id)] = a.user_answer
        }
        form.setFieldsValue({ answers: prefilled })
        if (startResp.answers.length > 0) {
          message.info(`已恢复 ${startResp.answers.length} 道题的已保存答案`)
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return
        message.error(err instanceof Error ? err.message : '开始考试失败')
        navigate('/practice', { replace: true })
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [paperId, form, navigate])

  const filledCount = questions.filter((q) => {
    const v = answers[String(q.id)]
    return typeof v === 'string' && v.trim().length > 0
  }).length

  // ---- 断点续考：防抖自动保存作答进度（仅进行中的会话）----
  const answersRef = useRef(answers)
  answersRef.current = answers

  const buildSavePayload = useCallback(() => {
    return Object.entries(answersRef.current)
      .filter(([, v]) => typeof v === 'string' && v.trim().length > 0)
      .map(([qid, v]) => ({ question_id: Number(qid), answer: v.trim() }))
  }, [])

  useEffect(() => {
    if (sessionId == null) return
    const timer = setTimeout(() => {
      const payload = buildSavePayload()
      if (payload.length === 0) return
      void examApi.save(sessionId, payload).catch(() => {
        /* 静默失败：不打断作答，提交时以整卷答案为准 */
      })
    }, 1500)
    return () => clearTimeout(timer)
  }, [answers, sessionId, buildSavePayload])

  // 离开页面时尽力保存最后一次作答
  useEffect(() => {
    if (sessionId == null) return
    const id = sessionId
    return () => {
      const payload = buildSavePayload()
      if (payload.length > 0) {
        void examApi.save(id, payload).catch(() => {})
      }
    }
  }, [sessionId, buildSavePayload])

  const onSubmit = async () => {
    if (sessionId == null) return
    setSubmitting(true)
    try {
      const payload = questions.map((q) => ({
        question_id: q.id,
        answer: (answers[String(q.id)] ?? '').trim(),
      }))
      const result = await examApi.submit(sessionId, payload)
      message.success(
        `提交成功：得分 ${result.total_score}/${result.max_score}（${(result.score_rate * 100).toFixed(1)}%）`,
      )
      setConfirmOpen(false)
      navigate(`/result/${sessionId}`)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '提交失败')
    } finally {
      setSubmitting(false)
    }
  }

  const renderQuestion = (q: ExamQuestion, index: number) => (
    <Card
      key={q.id}
      style={{ marginBottom: 16 }}
      title={
        <Space size={8}>
          <Typography.Text strong>第 {index + 1} 题</Typography.Text>
          <Tag color={Q_TYPE_COLOR[q.q_type]}>{Q_TYPE_TEXT[q.q_type]}</Tag>
          <Tag color={DIFFICULTY_COLOR[q.difficulty]}>{DIFFICULTY_TEXT[q.difficulty]}</Tag>
          {answers[String(q.id)] && (
            <Tag icon={<CheckCircleOutlined />} color="success">
              已作答
            </Tag>
          )}
        </Space>
      }
    >
      <Typography.Paragraph style={{ fontSize: 15, whiteSpace: 'pre-wrap' }}>
        {q.content}
      </Typography.Paragraph>
      {q.q_type === 'choice' && (
        <Form.Item name={`answers.${q.id}`} noStyle>
          <Radio.Group style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {(q.options ?? []).map((opt) => (
              <Radio key={opt} value={opt} style={{ marginLeft: 0 }}>
                {opt}
              </Radio>
            ))}
          </Radio.Group>
        </Form.Item>
      )}
      {q.q_type === 'judge' && (
        <Form.Item name={`answers.${q.id}`} noStyle>
          <Radio.Group style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {JUDGE_OPTIONS.map((opt) => (
              <Radio key={opt.value} value={opt.value} style={{ marginLeft: 0 }}>
                {opt.label}
              </Radio>
            ))}
          </Radio.Group>
        </Form.Item>
      )}
      {q.q_type === 'fill' && (
        <Form.Item name={`answers.${q.id}`} noStyle>
          <Input style={{ width: 400 }} placeholder="请输入答案" />
        </Form.Item>
      )}
    </Card>
  )

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Spin size="large" tip="正在载入试卷…">
          <div style={{ padding: 40 }} />
        </Spin>
      </div>
    )
  }

  if (questions.length === 0) {
    return (
      <Card>
        <Empty description="暂无题目，考卷可能为空或已失效">
          <Button type="primary" onClick={() => navigate('/practice')}>
            返回做题训练
          </Button>
        </Empty>
      </Card>
    )
  }

  return (
    <div>
      <Alert
        type="info"
        showIcon
        message={paperTitle}
        description={`共 ${questions.length} 题；支持断点续考，中途退出后再次进入将恢复已填答案。未作答题目按未答处理。`}
        style={{ marginBottom: 16 }}
      />

      <Form form={form} layout="vertical" disabled={submitting}>
        {questions.map((q, i) => renderQuestion(q, i))}
      </Form>

      <Card>
        <Row justify="space-between" align="middle" gutter={16}>
          <Space size={48} wrap>
            <Statistic title="总题数" value={questions.length} />
            <Statistic title="已作答" value={filledCount} valueStyle={{ color: '#3f8600' }} />
            <Statistic
              title="未作答"
              value={questions.length - filledCount}
              valueStyle={{ color: '#cf1322' }}
            />
          </Space>
          <Button type="primary" size="large" loading={submitting} onClick={() => setConfirmOpen(true)}>
            提交答卷
          </Button>
        </Row>
      </Card>

      <Modal
        title="确认提交答卷"
        open={confirmOpen}
        onOk={() => void onSubmit()}
        onCancel={() => setConfirmOpen(false)}
        okText="确认提交"
        cancelText="继续作答"
        confirmLoading={submitting}
      >
        <Typography.Paragraph>
          本次共 {questions.length} 题，已作答 <Typography.Text strong>{filledCount}</Typography.Text> 题，
          未作答 <Typography.Text strong>{questions.length - filledCount}</Typography.Text> 题。
        </Typography.Paragraph>
        <Typography.Paragraph type="secondary">
          提交后将进行评分并锁定答案，不可修改。未作答题目按未答处理（不计分）。
        </Typography.Paragraph>
      </Modal>
    </div>
  )
}
