import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import Layout from './components/Layout'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import VerifyPage from './pages/VerifyPage'
import ForgotPasswordPage from './pages/ForgotPasswordPage'
import CandidateDashboard from './pages/candidate/Dashboard'
import CandidateProfile from './pages/candidate/Profile'
import CandidateResults from './pages/candidate/Results'
import CandidateOffers from './pages/candidate/Offers'
import EmployerDashboard from './pages/employer/Dashboard'
import EmployerSearch from './pages/employer/Search'
import EmployerNeeds from './pages/employer/Needs'
import EmployerOffers from './pages/employer/Offers'
import EmployerVacancies from './pages/employer/Vacancies'
import EmployerCompany from './pages/employer/Company'
import CandidateVacancies from './pages/candidate/Vacancies'
import CandidateAssessment from './pages/candidate/Assessment'
import LeaderboardPage from './pages/LeaderboardPage'
import PublicProfile from './pages/PublicProfile'
import NotFoundPage from './pages/NotFoundPage'
import LegalPage from './pages/LegalPage'
import FspIdDemoPage from './pages/FspIdDemoPage'
import FspCallback from './pages/candidate/FspCallback'
import CandidateTasks from './pages/candidate/Tasks'
import EmployerTasks from './pages/employer/Tasks'
import FspSignInCallback from './pages/FspSignInCallback'

function ProtectedRoute({ children, role }: { children: React.ReactNode; role: 'participant' | 'employer' }) {
  const { token, userRole } = useAuthStore()
  if (!token) return <Navigate to="/login" replace />
  if (userRole !== role) return <Navigate to="/" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/verify" element={<VerifyPage />} />
        <Route path="/forgot" element={<ForgotPasswordPage />} />
        <Route path="/leaderboard" element={<LeaderboardPage />} />
        <Route path="/legal" element={<LegalPage />} />
        <Route path="/p/:id" element={<PublicProfile />} />
        <Route path="/fsp-id/authorize" element={<FspIdDemoPage />} />
        <Route path="/auth/fsp-callback" element={<FspSignInCallback />} />

        {/* Candidate area */}
        <Route path="/candidate" element={<ProtectedRoute role="participant"><Layout /></ProtectedRoute>}>
          <Route index element={<CandidateDashboard />} />
          <Route path="profile" element={<CandidateProfile />} />
          <Route path="results" element={<CandidateResults />} />
          <Route path="offers" element={<CandidateOffers />} />
          <Route path="vacancies" element={<CandidateVacancies />} />
          <Route path="assessment" element={<CandidateAssessment />} />
          <Route path="tasks" element={<CandidateTasks />} />
          <Route path="fsp-callback" element={<FspCallback />} />
        </Route>

        {/* Employer area */}
        <Route path="/employer" element={<ProtectedRoute role="employer"><Layout /></ProtectedRoute>}>
          <Route index element={<EmployerDashboard />} />
          <Route path="needs" element={<EmployerNeeds />} />
          <Route path="search" element={<EmployerSearch />} />
          <Route path="offers" element={<EmployerOffers />} />
          <Route path="vacancies" element={<EmployerVacancies />} />
          <Route path="tasks" element={<EmployerTasks />} />
          <Route path="company" element={<EmployerCompany />} />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  )
}
