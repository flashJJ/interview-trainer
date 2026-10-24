import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Badge, Layout, Menu, Dropdown, Avatar, Space, Typography } from 'antd'
import {
  BookOutlined,
  QuestionCircleOutlined,
  EditOutlined,
  CarryOutOutlined,
  AuditOutlined,
  BarChartOutlined,
  LineChartOutlined,
  SettingOutlined,
  UserOutlined,
  LogoutOutlined,
} from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { useEffect, useState } from 'react'
import { useAuth } from '../store/auth'
import { questionApi } from '../api/client'

const { Header, Sider, Content } = Layout
const { Text } = Typography

export default function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuth()
  const [pendingCount, setPendingCount] = useState(0)

  // 待审核题目数（菜单徽标 + 30s 轮询）
  useEffect(() => {
    let timer: number | undefined
    const fetchPending = () => {
      questionApi
        .statsOverview()
        .then((s) => setPendingCount(s.pending_count ?? 0))
        .catch(() => {})
    }
    fetchPending()
    timer = window.setInterval(fetchPending, 30000)
    return () => {
      if (timer) window.clearInterval(timer)
    }
  }, [])

  const reviewLabel =
    pendingCount > 0 ? (
      <Badge count={pendingCount} size="small" offset={[8, 0]}>
        <span style={{ marginRight: 12 }}>题目审核</span>
      </Badge>
    ) : (
      '题目审核'
    )

  const menuItems: MenuProps['items'] = [
    { key: '/knowledge', icon: <BookOutlined />, label: '知识库' },
    { key: '/questions', icon: <QuestionCircleOutlined />, label: '题库' },
    { key: '/practice', icon: <EditOutlined />, label: '做题训练' },
    { key: '/wrong-questions', icon: <CarryOutOutlined />, label: '错题本' },
    { key: '/review', icon: <AuditOutlined />, label: reviewLabel },
    { key: '/analytics/questions', icon: <BarChartOutlined />, label: '题目分析' },
    { key: '/analytics/practice', icon: <LineChartOutlined />, label: '做题分析' },
    { key: '/settings', icon: <SettingOutlined />, label: '系统配置' },
  ]

  const selectedKey =
    menuItems
      ?.map((i) => i?.key as string)
      .filter((k) => k && location.pathname.startsWith(k))
      .sort((a, b) => b.length - a.length)[0] ?? '/knowledge'

  const userMenu: MenuProps['items'] = [
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: () => {
        logout()
        navigate('/login', { replace: true })
      },
    },
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider breakpoint="lg" collapsedWidth="0" theme="dark">
        <div
          style={{
            height: 56,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontWeight: 600,
            fontSize: 16,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
          }}
        >
          面试题训练系统
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: '#fff',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            boxShadow: '0 1px 4px rgba(0,21,41,0.08)',
          }}
        >
          <Dropdown menu={{ items: userMenu }} placement="bottomRight">
            <Space style={{ cursor: 'pointer' }}>
              <Avatar size="small" icon={<UserOutlined />} />
              <Text strong>{user?.username ?? '未登录'}</Text>
            </Space>
          </Dropdown>
        </Header>
        <Content style={{ margin: 24, padding: 24, background: '#f5f5f5' }}>
          <div
            style={{
              background: '#fff',
              borderRadius: 8,
              padding: 24,
              minHeight: 'calc(100vh - 160px)',
            }}
          >
            <Outlet />
          </div>
        </Content>
      </Layout>
    </Layout>
  )
}
