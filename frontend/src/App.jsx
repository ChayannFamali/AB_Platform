import {
  BrowserRouter,
  Link,
  Navigate,
  Route,
  Routes,
} from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useAuthStore } from './stores/authStore'
import { useUiStore } from './stores/uiStore'
import { Button } from './components/ui/button'
import { Badge } from './components/ui/badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from './components/ui/dropdown-menu'
import { Toaster } from './components/ui/toaster'
import PageContainer from './components/PageContainer'

import ApiKeysPage from './pages/ApiKeysPage'
import AuditLogPage from './pages/AuditLogPage'
import CreateExperiment from './pages/CreateExperiment'
import ExperimentList from './pages/ExperimentList'
import ExperimentResults from './pages/ExperimentResults'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import UsersPage from './pages/UsersPage'

function ProtectedRoute({ children }) {
  const isAuthenticated = useAuthStore((s) => Boolean(s.user && s.token))
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  const { t } = useTranslation()
  const logout = useAuthStore((s) => s.logout)
  const user = useAuthStore((s) => s.user)
  const roles = useAuthStore((s) => s.roles)
  const toggleTheme = useUiStore((s) => s.toggleTheme)
  const theme = useUiStore((s) => s.theme)
  const setLocale = useUiStore((s) => s.setLocale)
  const locale = useUiStore((s) => s.locale)

  const handleLogout = () => {
    logout()
  }

  const isAuthenticated = Boolean(user)

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-background text-foreground">
        {isAuthenticated && (
          <nav className="flex h-14 items-center gap-4 border-b bg-card px-4">
            <Link to="/" className="font-semibold">
              {t('common.appName')}
            </Link>
            <Link
              to="/"
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              {t('experiments.title')}
            </Link>
            <Link
              to="/experiments/new"
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              {t('experiments.new')}
            </Link>
            <Link
              to="/api-keys"
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              {t('apiKeys.title')}
            </Link>
            {Array.isArray(roles) && roles.includes('admin') && (
              <>
                <Link
                  to="/settings/users"
                  className="text-sm text-muted-foreground hover:text-foreground"
                >
                  {t('users.title')}
                </Link>
                <Link
                  to="/settings/audit"
                  className="text-sm text-muted-foreground hover:text-foreground"
                >
                  {t('audit.title')}
                </Link>
              </>
            )}

            <div className="ml-auto flex items-center gap-3">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="sm">
                    {locale === 'ru' ? 'Русский' : 'English'}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuLabel>{t('common.language')}</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onSelect={() => setLocale('ru')}>
                    Русский
                  </DropdownMenuItem>
                  <DropdownMenuItem onSelect={() => setLocale('en')}>
                    English
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>

              <Button variant="ghost" size="sm" onClick={toggleTheme}>
                {theme === 'dark'
                  ? t('common.lightMode')
                  : t('common.darkMode')}
              </Button>

              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">
                  {user?.username}
                </span>
                {Array.isArray(roles) && roles.includes('admin') && (
                  <Badge variant="default">admin</Badge>
                )}
              </div>

              <Button variant="secondary" size="sm" onClick={handleLogout}>
                {t('common.logout')}
              </Button>
            </div>
          </nav>
        )}

        <main>
          <Routes>
            {/* Public routes */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            {/* Protected routes */}
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <PageContainer>
                    <ExperimentList />
                  </PageContainer>
                </ProtectedRoute>
              }
            />
            <Route
              path="/experiments/new"
              element={
                <ProtectedRoute>
                  <PageContainer>
                    <CreateExperiment />
                  </PageContainer>
                </ProtectedRoute>
              }
            />
            <Route
              path="/experiments/:id"
              element={
                <ProtectedRoute>
                  <PageContainer>
                    <ExperimentResults />
                  </PageContainer>
                </ProtectedRoute>
              }
            />
            <Route
              path="/api-keys"
              element={
                <ProtectedRoute>
                  <PageContainer>
                    <ApiKeysPage />
                  </PageContainer>
                </ProtectedRoute>
              }
            />
            <Route
              path="/settings/users"
              element={
                <ProtectedRoute>
                  <PageContainer>
                    <UsersPage />
                  </PageContainer>
                </ProtectedRoute>
              }
            />
            <Route
              path="/settings/audit"
              element={
                <ProtectedRoute>
                  <PageContainer>
                    <AuditLogPage />
                  </PageContainer>
                </ProtectedRoute>
              }
            />

            <Route
              path="*"
              element={
                <Navigate to={isAuthenticated ? '/' : '/login'} replace />
              }
            />
          </Routes>
        </main>

        <Toaster />
      </div>
    </BrowserRouter>
  )
}