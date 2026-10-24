import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from './components/AppLayout'
import Login from './pages/Login'
import KnowledgeBase from './pages/KnowledgeBase'
import QuestionBank from './pages/QuestionBank'
import Review from './pages/Review'
import Practice from './pages/Practice'
import WrongQuestions from './pages/WrongQuestions'
import ExamSession from './pages/ExamSession'
import ExamResult from './pages/ExamResult'
import QuestionAnalytics from './pages/QuestionAnalytics'
import PracticeAnalytics from './pages/PracticeAnalytics'
import Settings from './pages/Settings'
import { useAuth } from './store/auth'

export default function App() {
  const { token } = useAuth()

  if (!token && window.location.pathname !== '/login') {
    return <Navigate to="/login" replace />
  }

  return (
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
  )
}
