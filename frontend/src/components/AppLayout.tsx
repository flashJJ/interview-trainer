import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Layout, Menu, Dropdown, Avatar, Space, Typography } from 'antd'
import {
  BookOutlined,
  QuestionCircleOutlined,
  EditOutlined,
  CarryOutOutlined,
  AuditOutlined,
  BarChartOutlined,
  LineChartOutlined,
  ExperimentOutlined,
  RadarChartOutlined,
  SettingOutlined,
  UserOutlined,
  LogoutOutlined,
} from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { useAuth } from '../store/auth'
import { useQuestionStats } from '@/hooks/useQuestions'

const { Header, Sider, Content } = Layout
const { Text } = Typography

export default function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuth()
  // 待审核题目数（菜单徽标，30s 自动刷新）——数据层交给 TanStack Query
  const { data: questionStats } = useQuestionStats(30_000)
  const pendingCount = questionStats?.pending_count ?? 0

  // 自定义徽标：antd Badge 会强制 color: rgba(0,0,0,0.88)（深色侧栏上文字变黑看不清），
  // 且其 style prop 不透传，故手写红点徽标并显式继承菜单文字颜色。
  const reviewLabel = (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color: 'inherit' }}>
      题目审核
      {pendingCount > 0 && (
        <span
          style={{
            background: '#ff4d4f',
            color: '#fff',
            borderRadius: 9,
            fontSize: 11,
            lineHeight: '16px',
            padding: '0 5px',
            minWidth: 16,
            textAlign: 'center',
            fontWeight: 500,
          }}
        >
          {pendingCount > 99 ? '99+' : pendingCount}
        </span>
      )}
    </span>
  )

  const menuItems: MenuProps['items'] = [
    { key: '/knowledge', icon: <BookOutlined />, label: '知识库' },
    { key: '/questions', icon: <QuestionCircleOutlined />, label: '题库' },
    { key: '/practice', icon: <EditOutlined />, label: '做题训练' },
    { key: '/wrong-questions', icon: <CarryOutOutlined />, label: '错题本' },
    { key: '/review', icon: <AuditOutlined />, label: reviewLabel },
    { key: '/analytics/questions', icon: <BarChartOutlined />, label: '题目分析' },
    { key: '/analytics/practice', icon: <LineChartOutlined />, label: '做题分析' },
    { key: '/retrieval', icon: <ExperimentOutlined />, label: '检索评测' },
    { key: '/mastery', icon: <RadarChartOutlined />, label: '掌握度' },
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
    <Layout style={{ height: '100vh', overflow: 'hidden' }}>
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
      <Layout style={{ minWidth: 0, height: '100vh' }}>
        <Header
          style={{
            background: '#fff',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            boxShadow: '0 1px 4px rgba(0,21,41,0.08)',
            flex: '0 0 auto',
            zIndex: 10,
          }}
        >
          <Dropdown menu={{ items: userMenu }} placement="bottomRight">
            <Space style={{ cursor: 'pointer' }}>
              <Avatar size="small" icon={<UserOutlined />} />
              <Text strong>{user?.username ?? '未登录'}</Text>
            </Space>
          </Dropdown>
        </Header>
        {/*
          内边距交给白色卡片自己承担（padding: 24）。
          Content 自身不能有 padding：Chrome 计算 position: sticky 的约束矩形时
          会把滚动容器的内边距算进去，导致固定表头吸附位置比内容区顶部低 24px，
          滚动的行会从这条缝里露出来。
        */}
        <Content
          style={{
            flex: 1,
            minHeight: 0,
            overflow: 'auto',
            margin: 24,
            background: '#f5f5f5',
          }}
        >
          {/*
            注意：这里不能加 overflow: 'hidden'。
            它会为 position: sticky 建立新的滚动容器（且自身不滚动），
            导致 Table 的固定表头失效（表头会跟着内容一起滚走）。
            横向溢出由各页 Table 的 scroll={{ x }} 自行处理。
          */}
          <div
            style={{
              background: '#fff',
              borderRadius: 8,
              padding: 24,
              minHeight: '100%',
              maxWidth: '100%',
            }}
          >
            <Outlet />
          </div>
        </Content>
      </Layout>
    </Layout>
  )
}
