import { useState } from 'react'
import { BrowserRouter, Link, NavLink, Navigate, Route, Routes } from 'react-router-dom'
import ApiKeysPage       from './pages/ApiKeysPage'
import CreateExperiment  from './pages/CreateExperiment'
import ExperimentList    from './pages/ExperimentList'
import ExperimentResults from './pages/ExperimentResults'
import LoginPage         from './pages/LoginPage'
import RegisterPage      from './pages/RegisterPage'
import './App.css'

function ProtectedRoute({ user, children }) {
  if (!user) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  const [user, setUser] = useState(() => {
    try {
      const s = localStorage.getItem('user')
      return s ? JSON.parse(s) : null
    } catch { return null }
  })

  const handleLogin  = (u) => setUser(u)
  const handleLogout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
    setUser(null)
  }

  return (
    <BrowserRouter>
      <div className="app">

        {user && (
          <nav>
            <Link to="/" className="brand">⚗️ AB Platform</Link>
            <NavLink to="/">Эксперименты</NavLink>
            <NavLink to="/experiments/new">+ Создать</NavLink>

            <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <NavLink to="/api-keys" style={{ fontSize: '0.85rem' }}>API Ключи</NavLink>
              <span style={{ color: '#9ca3af', fontSize: '0.85rem' }}>
                {user.username}
                {user.is_admin && (
                  <span style={{
                    marginLeft: '0.4rem', fontSize: '0.65rem',
                    background: '#4f46e5', color: '#fff',
                    padding: '0.1rem 0.4rem', borderRadius: '4px',
                    verticalAlign: 'middle',
                  }}>
                    admin
                  </span>
                )}
              </span>
              <button className="btn btn-sm btn-secondary" onClick={handleLogout}>
                Выйти
              </button>
            </div>
          </nav>
        )}

        <main style={!user ? { padding: 0, maxWidth: '100%' } : undefined}>
          <Routes>
            {/* Публичные */}
            <Route path="/login"    element={<LoginPage    onLogin={handleLogin} />} />
            <Route path="/register" element={<RegisterPage onLogin={handleLogin} />} />

            {/* Защищённые */}
            <Route path="/" element={
              <ProtectedRoute user={user}><ExperimentList /></ProtectedRoute>
            } />
            <Route path="/experiments/new" element={
              <ProtectedRoute user={user}><CreateExperiment /></ProtectedRoute>
            } />
            <Route path="/experiments/:id" element={
              <ProtectedRoute user={user}><ExperimentResults /></ProtectedRoute>
            } />
            <Route path="/api-keys" element={
              <ProtectedRoute user={user}><ApiKeysPage /></ProtectedRoute>
            } />

            <Route path="*" element={<Navigate to={user ? '/' : '/login'} replace />} />
          </Routes>
        </main>

      </div>
    </BrowserRouter>
  )
}
