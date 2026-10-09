import { lazy, Suspense, useEffect, useState, type ComponentType, type ReactNode } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { renewAccess } from './api/client'
import { useAuthStore } from './store/authStore'
import { Skeleton } from './components/ui'

function RouteFallback() {
  return (
    <div className="mx-auto min-h-[70vh] w-full max-w-5xl px-4 py-8">
      <p className="sr-only" role="status">Загрузка</p>
      <Skeleton className="h-64" />
    </div>
  )
}

function page(loader: () => Promise<{ default: ComponentType }>) {
  const Page = lazy(loader)
  return function LazyPage() {
    return (
      <Suspense fallback={<RouteFallback />}>
        <Page />
      </Suspense>
    )
  }
}

const QueryShell = page(() => import('./QueryShell'))
const Layout = page(() => import('./components/Layout'))
const LandingPage = page(() => import('./pages/LandingPage'))
const LoginPage = page(() => import('./pages/LoginPage'))
const RegisterPage = page(() => import('./pages/RegisterPage'))
const VerifyPage = page(() => import('./pages/VerifyPage'))
const GuardianPage = page(() => import('./pages/GuardianPage'))
const ForgotPasswordPage = page(() => import('./pages/ForgotPasswordPage'))
const LeaderboardPage = page(() => import('./pages/LeaderboardPage'))
const PublicProfile = page(() => import('./pages/PublicProfile'))
const NotFoundPage = page(() => import('./pages/NotFoundPage'))
const LegalPage = page(() => import('./pages/LegalPage'))
const FspIdDemoPage = page(() => import('./pages/FspIdDemoPage'))
const FspSignInCallback = page(() => import('./pages/FspSignInCallback'))
const MethodPage = page(() => import('./pages/MethodPage'))
const BadgePage = page(() => import('./pages/BadgePage'))
const JuryPage = page(() => import('./pages/JuryPage'))

const CandidateDashboard = page(() => import('./pages/candidate/Dashboard'))
const CandidateProfile = page(() => import('./pages/candidate/Profile'))
const CandidateResults = page(() => import('./pages/candidate/Results'))
const CandidateOffers = page(() => import('./pages/candidate/Offers'))
const CandidateVacancies = page(() => import('./pages/candidate/Vacancies'))
const CandidateAssessment = page(() => import('./pages/candidate/Assessment'))
const CandidateTasks = page(() => import('./pages/candidate/Tasks'))
const FspCallback = page(() => import('./pages/candidate/FspCallback'))

const EmployerDashboard = page(() => import('./pages/employer/Dashboard'))
const EmployerSearch = page(() => import('./pages/employer/Search'))
const EmployerNeeds = page(() => import('./pages/employer/Needs'))
const EmployerOffers = page(() => import('./pages/employer/Offers'))
const EmployerVacancies = page(() => import('./pages/employer/Vacancies'))
const EmployerCompany = page(() => import('./pages/employer/Company'))
const EmployerTasks = page(() => import('./pages/employer/Tasks'))
const EmployerModeration = page(() => import('./pages/employer/Moderation'))

function ProtectedRoute({ children, role }: { children: ReactNode; role: 'participant' | 'employer' }) {
  const { token, userRole, needsRenew } = useAuthStore()
  const [renewing, setRenewing] = useState(needsRenew)
  useEffect(() => {
    if (!needsRenew) {
      setRenewing(false)
      return
    }
    let live = true
    setRenewing(true)
    renewAccess().finally(() => { if (live) setRenewing(false) })
    return () => { live = false }
  }, [needsRenew])
  if (renewing) return <p className="sr-only" role="status">Вход</p>
  if (!token) return <Navigate to="/login" replace />
  if (userRole !== role) return <Navigate to="/" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route element={<QueryShell />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/verify" element={<VerifyPage />} />
        <Route path="/guardian" element={<GuardianPage />} />
        <Route path="/forgot" element={<ForgotPasswordPage />} />
        <Route path="/leaderboard" element={<LeaderboardPage />} />
        <Route path="/method" element={<MethodPage />} />
        <Route path="/jury" element={<JuryPage />} />
        <Route path="/badge" element={<BadgePage />} />
        <Route path="/legal" element={<LegalPage />} />
        <Route path="/p/:id" element={<PublicProfile />} />
        <Route path="/fsp-id/authorize" element={<FspIdDemoPage />} />
        <Route path="/auth/fsp-callback" element={<FspSignInCallback />} />

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

        <Route path="/employer" element={<ProtectedRoute role="employer"><Layout /></ProtectedRoute>}>
          <Route index element={<EmployerDashboard />} />
          <Route path="needs" element={<EmployerNeeds />} />
          <Route path="search" element={<EmployerSearch />} />
          <Route path="offers" element={<EmployerOffers />} />
          <Route path="vacancies" element={<EmployerVacancies />} />
          <Route path="tasks" element={<EmployerTasks />} />
          <Route path="company" element={<EmployerCompany />} />
          <Route path="moderation" element={<EmployerModeration />} />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
