import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { Spin } from 'antd'
import AppLayout from './components/AppLayout'
import { useAuth } from './store/auth'

// 路由级代码分割：每个页面独立 chunk，首屏只加载登录页
const Login = lazy(() => import('./pages/Login'))
const KnowledgeBase = lazy(() => import('./pages/KnowledgeBase'))
const QuestionBank = lazy(() => import('./pages/QuestionBank'))
const Review = lazy(() => import('./pages/Review'))
const Practice = lazy(() => import('./pages/Practice'))
const WrongQuestions = lazy(() => import('./pages/WrongQuestions'))
const ExamSession = lazy(() => import('./pages/ExamSession'))
const ExamResult = lazy(() => import('./pages/ExamResult'))
const QuestionAnalytics = lazy(() => import('./pages/QuestionAnalytics'))
const PracticeAnalytics = lazy(() => import('./pages/PracticeAnalytics'))
const Settings = lazy(() => import('./pages/Settings'))

function PageLoading() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: 80 }}>
      <Spin size="large" tip="页面加载中…">
        <div style={{ padding: 40 }} />
      </Spin>
    </div>
  )
}

export default function App() {
  const { token } = useAuth()

  if (!token && window.location.pathname !== '/login') {
    return <Navigate to="/login" replace />
  }

  return (
    <Suspense fallback={<PageLoading />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<AppLayout />}>
          <Route path="/knowledge" element={<KnowledgeBase />} />
          <Route path="/questions" element={<QuestionBank />} />
          <Route path="/review" element={<Review />} />
          <Route path="/practice" element={<Practice />} />
          <Route path="/wrong-questions" element={<WrongQuestions />} />
          <Route path="/exam/:paperId" element={<ExamSession />} />
          <Route path="/result/:sessionId" element={<ExamResult />} />
          <Route path="/analytics/questions" element={<QuestionAnalytics />} />
          <Route path="/analytics/practice" element={<PracticeAnalytics />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/knowledge" replace />} />
      </Routes>
    </Suspense>
  )
}
