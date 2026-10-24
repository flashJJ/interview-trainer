import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button, Card, Col, Descriptions, Empty, Radio, Row, Space, Spin, Statistic, Tag, Typography } from 'antd'
import { App as AntdApp } from 'antd'
import { CarryOutOutlined, RobotOutlined } from '@ant-design/icons'
import { examApi } from '../api/client'
import AITutorDrawer from '../components/AITutorDrawer'
import type { SessionDetailResp, SubmitResultItem } from '../api/types'
import {
  fmtDuration,
  pct,
  Q_TYPE_COLOR,
  Q_TYPE_TEXT,
} from '../utils/constants'

function AnswerText({ q, user }: { q: SubmitResultItem; user: string | null }) {
  if (user === null || user === '') {
    return <Typography.Text type="secondary">未作答</Typography.Text>
  }
  const isCorrect = q.is_correct
  return (
    <Typography.Text strong style={{ color: isCorrect ? '#3f8600' : '#cf1322' }}>
      {user}
    </Typography.Text>
  )
}

export default function ExamResult() {
  const [tutorOpen, setTutorOpen] = useState(false)
  const [tutorQuestionId, setTutorQuestionId] = useState<number | null>(null)
  const [tutorTitle, setTutorTitle] = useState('')

  const { message } = AntdApp.useApp()
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState<SessionDetailResp | null>(null)

  const load = useCallback(async () => {
    if (!sessionId) return
    setLoading(true)
    try {
      const resp = await examApi.getSession(Number(sessionId))
      setData(resp)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '获取成绩详情失败')
      navigate('/practice', { replace: true })
    } finally {
      setLoading(false)
    }
  }, [sessionId, navigate])

  useEffect(() => {
    void load()
  }, [load])

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Spin size="large" tip="正在载入成绩…">
          <div style={{ padding: 40 }} />
        </Spin>
      </div>
    )
  }

  if (!data) {
    return (
      <Card>
        <Empty description="成绩不存在或已失效">
          <Button type="primary" onClick={() => navigate('/practice')}>
            返回做题训练
          </Button>
        </Empty>
      </Card>
    )
  }

  const scoreRatePct = pct(data.score_rate)

  return (
    <div>
      <AITutorDrawer
        questionId={tutorQuestionId}
        questionTitle={tutorTitle}
        open={tutorOpen}
        onClose={() => setTutorOpen(false)}
      />
      <Card title="考试结果" style={{ marginBottom: 16 }}>
        <Row gutter={16}>
          <Col span={6}>
            <Statistic
              title="总分"
              value={data.total_score}
              suffix={`/ ${data.max_score}`}
              valueStyle={{ color: data.score_rate >= 0.6 ? '#3f8600' : '#cf1322' }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="得分率"
              value={scoreRatePct}
              valueStyle={{ color: data.score_rate >= 0.6 ? '#3f8600' : '#cf1322' }}
            />
          </Col>
          <Col span={6}>
            <Statistic title="正确题数" value={`${data.correct_count} / ${data.question_count}`} />
          </Col>
          <Col span={6}>
            <Statistic title="用时" value={fmtDuration(data.duration_sec)} />
          </Col>
        </Row>
      </Card>

      <Typography.Title level={5} style={{ marginBottom: 16 }}>
        逐题反馈
      </Typography.Title>

      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        {data.results.map((q, i) => (
          <Card
            key={q.question_id}
            size="small"
            title={
              <Space size={8} wrap>
                <Typography.Text strong>第 {i + 1} 题</Typography.Text>
                <Tag color={Q_TYPE_COLOR[q.q_type]}>{Q_TYPE_TEXT[q.q_type]}</Tag>
                <Tag color={q.score > 0 ? 'green' : 'default'}>
                  {q.score} / {q.max_score}
                </Tag>
                <Tag color={q.ai_source === 'llm' ? 'magenta' : 'default'}>
                  {q.ai_source === 'llm' ? 'AI 评分' : '规则评分'}
                </Tag>
                {!q.is_correct && (
                  <Tag color="orange" icon={<CarryOutOutlined />}>
                    已计入错题本
                  </Tag>
                )}
                <Button
                  type="link"
                  size="small"
                  icon={<RobotOutlined />}
                  onClick={() => {
                    setTutorQuestionId(q.question_id)
                    setTutorTitle(q.content)
                    setTutorOpen(true)
                  }}
                >
                  问 AI
                </Button>
              </Space>
            }
          >
            <Typography.Paragraph strong style={{ whiteSpace: 'pre-wrap' }}>
              {q.content}
            </Typography.Paragraph>

            {q.options && q.options.length > 0 && (
              <Radio.Group
                value={q.user_answer ?? undefined}
                disabled
                style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 12 }}
              >
                {q.options.map((opt) => {
                  const isAnswer = opt === q.answer || opt.startsWith(q.answer)
                  const isUser = opt === q.user_answer
                  return (
                    <Radio
                      key={opt}
                      value={opt}
                      style={{
                        marginLeft: 0,
                        color: isAnswer ? '#3f8600' : undefined,
                        fontWeight: isAnswer ? 600 : undefined,
                      }}
                    >
                      {opt}
                      {isAnswer && (
                        <Tag color="green" style={{ marginLeft: 8 }}>
                          标准答案
                        </Tag>
                      )}
                      {isUser && !isAnswer && (
                        <Tag color="red" style={{ marginLeft: 8 }}>
                          你的选择
                        </Tag>
                      )}
                      {isUser && isAnswer && (
                        <Tag color="green" style={{ marginLeft: 8 }}>
                          你的选择
                        </Tag>
                      )}
                    </Radio>
                  )
                })}
              </Radio.Group>
            )}

            {q.q_type === 'judge' && (
              <Radio.Group
                value={q.user_answer ?? undefined}
                disabled
                style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 12 }}
              >
                {['正确', '错误'].map((opt) => {
                  const isAnswer = opt === q.answer
                  const isUser = opt === q.user_answer
                  return (
                    <Radio
                      key={opt}
                      value={opt}
                      style={{
                        marginLeft: 0,
                        color: isAnswer ? '#3f8600' : undefined,
                        fontWeight: isAnswer ? 600 : undefined,
                      }}
                    >
                      {opt}
                      {isAnswer && (
                        <Tag color="green" style={{ marginLeft: 8 }}>
                          标准答案
                        </Tag>
                      )}
                      {isUser && !isAnswer && (
                        <Tag color="red" style={{ marginLeft: 8 }}>
                          你的选择
                        </Tag>
                      )}
                      {isUser && isAnswer && (
                        <Tag color="green" style={{ marginLeft: 8 }}>
                          你的选择
                        </Tag>
                      )}
                    </Radio>
                  )
                })}
              </Radio.Group>
            )}

            <Descriptions column={1} size="small" style={{ marginBottom: 12 }}>
              <Descriptions.Item label="你的答案">
                <AnswerText q={q} user={q.user_answer} />
              </Descriptions.Item>
              <Descriptions.Item label="标准答案">
                <Typography.Text strong style={{ color: '#3f8600' }}>
                  {q.answer}
                </Typography.Text>
              </Descriptions.Item>
              <Descriptions.Item label="得分 Badge">
                <Tag
                  color={q.score >= q.max_score ? 'green' : q.score > 0 ? 'gold' : 'red'}
                  style={{ fontSize: 14, padding: '2px 10px' }}
                >
                  {q.score} / {q.max_score}
                </Tag>
                {q.is_correct ? (
                  <Tag color="success" style={{ marginLeft: 8 }}>
                    正确
                  </Tag>
                ) : (
                  <Tag color="error" style={{ marginLeft: 8 }}>
                    {q.user_answer === null || q.user_answer === '' ? '未作答' : '错误'}
                  </Tag>
                )}
              </Descriptions.Item>
              {q.feedback && (
                <Descriptions.Item label="AI 评语">
                  <Typography.Text>{q.feedback}</Typography.Text>
                </Descriptions.Item>
              )}
              {q.explanation && (
                <Descriptions.Item label="解析">
                  <Typography.Text type="secondary">{q.explanation}</Typography.Text>
                </Descriptions.Item>
              )}
            </Descriptions>
          </Card>
        ))}
      </Space>

      <div style={{ marginTop: 24, textAlign: 'center' }}>
        <Space size={16}>
          <Button type="primary" onClick={() => navigate('/practice')}>
            返回做题训练
          </Button>
          <Button onClick={() => navigate('/analytics/practice')}>
            查看做题分析
          </Button>
        </Space>
      </div>
    </div>
  )
}
