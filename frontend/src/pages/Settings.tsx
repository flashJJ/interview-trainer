import { useEffect, useState } from 'react'
import {
  Alert,
  App as AntdApp,
  Button,
  Card,
  Descriptions,
  Divider,
  Form,
  Input,
  InputNumber,
  Popconfirm,
  Space,
  Spin,
  Tabs,
  Tag,
  Typography,
} from 'antd'
import {
  ApiOutlined,
  CloudServerOutlined,
  SaveOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { settingsApi } from '../api/client'
import type { SystemConfig, TestConnectionResult } from '../api/types'

interface LLMFormValues {
  llm_base_url: string
  llm_api_key: string
  llm_model: string
  llm_timeout_seconds: number
  embedding_base_url: string
  embedding_api_key: string
  embedding_model: string
}

interface PasswordFormValues {
  old_password: string
  new_password: string
  confirm_password: string
}

export default function Settings() {
  const { message } = AntdApp.useApp()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [config, setConfig] = useState<SystemConfig | null>(null)
  const [testing, setTesting] = useState<'llm' | 'embedding' | null>(null)
  const [form] = Form.useForm<LLMFormValues>()
  const [pwdForm] = Form.useForm<PasswordFormValues>()

  const loadConfig = async () => {
    setLoading(true)
    try {
      const data = await settingsApi.get()
      setConfig(data)
      form.setFieldsValue({
        llm_base_url: data.llm_base_url,
        llm_api_key: '', // 已配置时留空 = 不修改
        llm_model: data.llm_model,
        llm_timeout_seconds: data.llm_timeout_seconds,
        embedding_base_url: data.embedding_base_url,
        embedding_api_key: '',
        embedding_model: data.embedding_model,
      })
    } catch (err) {
      message.error(err instanceof Error ? err.message : '加载配置失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadConfig()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const onSave = async (values: LLMFormValues) => {
    setSaving(true)
    try {
      // API Key 留空表示不修改；空 Base URL 表示清空该项
      const payload = {
        llm_base_url: values.llm_base_url?.trim() ?? '',
        llm_api_key: values.llm_api_key?.trim() || null,
        llm_model: values.llm_model?.trim() ?? '',
        llm_timeout_seconds: values.llm_timeout_seconds,
        embedding_base_url: values.embedding_base_url?.trim() ?? '',
        embedding_api_key: values.embedding_api_key?.trim() || null,
        embedding_model: values.embedding_model?.trim() ?? '',
      }
      const data = await settingsApi.save(payload)
      setConfig(data)
      message.success(
        data.llm_enabled ? '配置已保存并生效：AI 模式已启用' : '配置已保存并生效：当前为演示模式',
      )
    } catch (err) {
      message.error(err instanceof Error ? err.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const onTest = async (target: 'llm' | 'embedding') => {
    const values = form.getFieldsValue()
    setTesting(target)
    try {
      const payload =
        target === 'llm'
          ? {
              target,
              llm_base_url: values.llm_base_url?.trim(),
              llm_api_key: values.llm_api_key?.trim() || undefined,
              llm_model: values.llm_model?.trim(),
            }
          : {
              target,
              embedding_base_url: values.embedding_base_url?.trim(),
              embedding_api_key: values.embedding_api_key?.trim() || undefined,
              embedding_model: values.embedding_model?.trim(),
            }
      const result: TestConnectionResult = await settingsApi.test(payload)
      if (result.ok) {
        message.success(`${result.detail}（耗时 ${result.latency_ms}ms）`)
      } else {
        message.error(`连接失败：${result.error}`)
      }
    } catch (err) {
      message.error(err instanceof Error ? err.message : '测试失败')
    } finally {
      setTesting(null)
    }
  }

  const onReset = async () => {
    try {
      const data = await settingsApi.reset()
      setConfig(data)
      form.setFieldsValue({
        llm_base_url: data.llm_base_url,
        llm_api_key: '',
        llm_model: data.llm_model,
        llm_timeout_seconds: data.llm_timeout_seconds,
        embedding_base_url: data.embedding_base_url,
        embedding_api_key: '',
        embedding_model: data.embedding_model,
      })
      message.success('已恢复为 .env 默认配置')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '恢复默认失败')
    }
  }

  const onChangePassword = async (values: PasswordFormValues) => {
    try {
      const result = await settingsApi.changePassword(values.old_password, values.new_password)
      message.success(result.message)
      pwdForm.resetFields()
    } catch (err) {
      message.error(err instanceof Error ? err.message : '修改失败')
    }
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Spin size="large" tip="正在加载配置…">
          <div style={{ padding: 40 }} />
        </Spin>
      </div>
    )
  }

  return (
    <div>
      <Typography.Title level={4}>系统配置</Typography.Title>
      <Tabs
        defaultActiveKey="ai"
        items={[
          {
            key: 'ai',
            label: 'AI 模型配置',
            children: (
              <div style={{ maxWidth: 720 }}>
                <Alert
                  type={config?.llm_enabled ? 'success' : 'info'}
                  showIcon
                  style={{ marginBottom: 16 }}
                  message={
                    config?.llm_enabled
                      ? `AI 模式已启用（模型：${config.llm_model}）`
                      : '演示模式（未配置 LLM，使用内置规则引擎出题与评分）'
                  }
                  description={
                    <Space size={8} wrap>
                      <span>
                        Embedding：
                        {config?.embedding_mode === 'api' ? (
                          <Tag color="blue" icon={<ApiOutlined />}>
                            API 向量（{config.embedding_model}）
                          </Tag>
                        ) : (
                          <Tag icon={<CloudServerOutlined />}>内置确定性向量</Tag>
                        )}
                      </span>
                      <span>配置保存后即时生效，无需重启服务。</span>
                    </Space>
                  }
                />

                <Form<LLMFormValues>
                  form={form}
                  layout="vertical"
                  onFinish={onSave}
                  requiredMark={false}
                >
                  <Card size="small" title="LLM（出题 / 评分）" style={{ marginBottom: 16 }}>
                    <Form.Item
                      name="llm_base_url"
                      label="Base URL"
                      tooltip="任意 OpenAI 兼容协议的接口地址"
                      rules={[{ required: true, message: '请输入 Base URL（不启用 AI 模式可留空后保存）' }]}
                    >
                      <Input placeholder="例如 https://api.deepseek.com" allowClear />
                    </Form.Item>
                    <Form.Item
                      name="llm_api_key"
                      label="API Key"
                      tooltip={config?.llm_api_key_set ? '已配置，留空表示不修改' : '尚未配置'}
                    >
                      <Input.Password
                        placeholder={config?.llm_api_key_set ? config.llm_api_key_masked : 'sk-...'}
                        allowClear
                      />
                    </Form.Item>
                    <Form.Item name="llm_model" label="模型" rules={[{ required: true }]}>
                      <Input placeholder="例如 deepseek-chat / qwen-plus / gpt-4o-mini" allowClear />
                    </Form.Item>
                    <Form.Item name="llm_timeout_seconds" label="超时时间（秒）">
                      <InputNumber min={10} max={600} style={{ width: '100%' }} />
                    </Form.Item>
                    <Button
                      icon={<ThunderboltOutlined />}
                      loading={testing === 'llm'}
                      onClick={() => void onTest('llm')}
                    >
                      测试 LLM 连接
                    </Button>
                  </Card>

                  <Card size="small" title="Embedding（可选，不配置则使用内置向量）" style={{ marginBottom: 16 }}>
                    <Form.Item name="embedding_base_url" label="Base URL">
                      <Input placeholder="例如 https://api.siliconflow.cn/v1" allowClear />
                    </Form.Item>
                    <Form.Item name="embedding_api_key" label="API Key">
                      <Input.Password
                        placeholder={
                          config?.embedding_api_key_set ? config.embedding_api_key_masked : 'sk-...'
                        }
                        allowClear
                      />
                    </Form.Item>
                    <Form.Item name="embedding_model" label="模型">
                      <Input placeholder="例如 BAAI/bge-m3" allowClear />
                    </Form.Item>
                    <Button
                      icon={<ThunderboltOutlined />}
                      loading={testing === 'embedding'}
                      onClick={() => void onTest('embedding')}
                    >
                      测试 Embedding 连接
                    </Button>
                  </Card>

                  <Space>
                    <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={saving}>
                      保存配置
                    </Button>
                    <Popconfirm
                      title="恢复默认配置"
                      description="将清除本页保存的全部配置，回退到 .env 文件中的设置，确定吗？"
                      onConfirm={onReset}
                      okText="确定恢复"
                      cancelText="取消"
                    >
                      <Button>恢复 .env 默认</Button>
                    </Popconfirm>
                  </Space>
                </Form>

                <Divider />
                <Descriptions title="当前生效配置" size="small" column={1} bordered>
                  <Descriptions.Item label="运行模式">
                    {config?.llm_enabled ? 'AI 模式（LLM 出题 + LLM 评分）' : '演示模式（规则引擎）'}
                  </Descriptions.Item>
                  <Descriptions.Item label="LLM 地址">{config?.llm_base_url || '（未配置）'}</Descriptions.Item>
                  <Descriptions.Item label="LLM Key">
                    {config?.llm_api_key_set ? config.llm_api_key_masked : '（未配置）'}
                  </Descriptions.Item>
                  <Descriptions.Item label="Embedding 地址">
                    {config?.embedding_base_url || '（未配置，使用内置向量）'}
                  </Descriptions.Item>
                </Descriptions>
              </div>
            ),
          },
          {
            key: 'account',
            label: '账号安全',
            children: (
              <div style={{ maxWidth: 480 }}>
                <Alert
                  type="info"
                  showIcon
                  style={{ marginBottom: 16 }}
                  message="修改密码后需要退出并重新登录"
                />
                <Form<PasswordFormValues>
                  form={pwdForm}
                  layout="vertical"
                  onFinish={onChangePassword}
                  requiredMark={false}
                >
                  <Form.Item name="old_password" label="原密码" rules={[{ required: true }]}>
                    <Input.Password placeholder="请输入原密码" />
                  </Form.Item>
                  <Form.Item
                    name="new_password"
                    label="新密码"
                    rules={[{ required: true, min: 6, message: '新密码至少 6 位' }]}
                  >
                    <Input.Password placeholder="至少 6 位" />
                  </Form.Item>
                  <Form.Item
                    name="confirm_password"
                    label="确认新密码"
                    dependencies={['new_password']}
                    rules={[
                      { required: true, message: '请确认新密码' },
                      ({ getFieldValue }) => ({
                        validator(_, value) {
                          if (!value || getFieldValue('new_password') === value) {
                            return Promise.resolve()
                          }
                          return Promise.reject(new Error('两次输入的密码不一致'))
                        },
                      }),
                    ]}
                  >
                    <Input.Password placeholder="再次输入新密码" />
                  </Form.Item>
                  <Button type="primary" htmlType="submit">
                    修改密码
                  </Button>
                </Form>
              </div>
            ),
          },
        ]}
      />
    </div>
  )
}
