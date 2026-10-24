import { Button, Form, Input, Modal, Select, Space, Alert } from 'antd'
import { RobotOutlined } from '@ant-design/icons'
import type { Difficulty, KnowledgeEntry, QType } from '@/api/types'
import { DIFFICULTIES, DIFFICULTY_TEXT, QTYPES, Q_TYPE_TEXT } from '@/utils/constants'

export interface GenForm {
  types: QType[]
  count_per_type: number
  difficulty?: Difficulty
}

interface GenerateQuestionsModalProps {
  entry: KnowledgeEntry | null
  loading: boolean
  onClose: () => void
  onSubmit: (values: GenForm) => void
}

/** AI 出题弹窗：选题型 / 每题型数量 / 难度。 */
export default function GenerateQuestionsModal({
  entry,
  loading,
  onClose,
  onSubmit,
}: GenerateQuestionsModalProps) {
  const [form] = Form.useForm<GenForm>()

  return (
    <Modal
      title={`AI 出题 - ${entry?.title ?? ''}`}
      open={entry !== null}
      onCancel={onClose}
      footer={null}
      forceRender
      destroyOnHidden
    >
      <Form<GenForm>
        layout="vertical"
        form={form}
        initialValues={{ types: [...QTYPES], count_per_type: 3 }}
        onFinish={onSubmit}
      >
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
            <Button onClick={onClose}>取消</Button>
            <Button type="primary" htmlType="submit" icon={<RobotOutlined />} loading={loading}>
              开始生成
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </Modal>
  )
}
