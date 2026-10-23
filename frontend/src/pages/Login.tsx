import { useEffect, useState } from 'react'
import { Card, Form, Input, Tabs, Button, Typography } from 'antd'
import { App as AntdApp } from 'antd'
import { UserOutlined, LockOutlined, MailOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../store/auth'

interface LoginForm {
  username: string
  password: string
}

interface RegisterForm {
  username: string
  password: string
  email?: string
}

export default function Login() {
  const { message } = AntdApp.useApp()
  const navigate = useNavigate()
  const { token, login, register } = useAuth()
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('login')

  useEffect(() => {
    if (token) navigate('/knowledge', { replace: true })
  }, [token, navigate])

  const onLogin = async (values: LoginForm) => {
    setLoading(true)
    try {
      await login(values.username, values.password)
      message.success('登录成功')
      navigate('/knowledge', { replace: true })
    } catch (err) {
      message.error(err instanceof Error ? err.message : '登录失败')
    } finally {
      setLoading(false)
    }
  }

  const onRegister = async (values: RegisterForm) => {
    setLoading(true)
    try {
      await register(values.username, values.password, values.email)
      message.success('注册成功，请登录')
      setActiveTab('login')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '注册失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #f0f5ff 0%, #e6fffb 100%)',
      }}
    >
      <Card style={{ width: 420, boxShadow: '0 8px 24px rgba(0,0,0,0.08)' }}>
        <Typography.Title level={3} style={{ textAlign: 'center', marginBottom: 24 }}>
          面试题训练系统
        </Typography.Title>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          centered
          items={[
            {
              key: 'login',
              label: '登录',
              children: (
                <Form<LoginForm> layout="vertical" onFinish={onLogin} requiredMark={false}>
                  <Form.Item
                    name="username"
                    label="用户名"
                    rules={[{ required: true, message: '请输入用户名' }]}
                  >
                    <Input prefix={<UserOutlined />} placeholder="请输入用户名" size="large" />
                  </Form.Item>
                  <Form.Item
                    name="password"
                    label="密码"
                    rules={[{ required: true, message: '请输入密码' }]}
                  >
                    <Input.Password
                      prefix={<LockOutlined />}
                      placeholder="请输入密码"
                      size="large"
                    />
                  </Form.Item>
                  <Form.Item style={{ marginBottom: 0 }}>
                    <Button type="primary" htmlType="submit" block size="large" loading={loading}>
                      登 录
                    </Button>
                  </Form.Item>
                </Form>
              ),
            },
            {
              key: 'register',
              label: '注册',
              children: (
                <Form<RegisterForm> layout="vertical" onFinish={onRegister} requiredMark={false}>
                  <Form.Item
                    name="username"
                    label="用户名"
                    rules={[
                      { required: true, message: '请输入用户名' },
                      { min: 2, max: 30, message: '用户名长度 2~30 个字符' },
                    ]}
                  >
                    <Input prefix={<UserOutlined />} placeholder="请输入用户名" size="large" />
                  </Form.Item>
                  <Form.Item
                    name="email"
                    label="邮箱（可选）"
                    rules={[{ type: 'email', message: '邮箱格式不正确' }]}
                  >
                    <Input prefix={<MailOutlined />} placeholder="请输入邮箱" size="large" />
                  </Form.Item>
                  <Form.Item
                    name="password"
                    label="密码"
                    rules={[
                      { required: true, message: '请输入密码' },
                      { min: 6, message: '密码至少 6 位' },
                    ]}
                  >
                    <Input.Password
                      prefix={<LockOutlined />}
                      placeholder="请输入密码（至少 6 位）"
                      size="large"
                    />
                  </Form.Item>
                  <Form.Item style={{ marginBottom: 0 }}>
                    <Button type="primary" htmlType="submit" block size="large" loading={loading}>
                      注 册
                    </Button>
                  </Form.Item>
                </Form>
              ),
            },
          ]}
        />
      </Card>
    </div>
  )
}
