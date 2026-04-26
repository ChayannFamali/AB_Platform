import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { register, login } from '../api/client'

export default function RegisterPage({ onLogin }) {
  const [form,    setForm]    = useState({ username: '', email: '', password: '', confirm: '' })
  const [error,   setError]   = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (form.password !== form.confirm) {
      setError('Пароли не совпадают')
      return
    }

    setLoading(true)
    try {
      await register({ username: form.username, email: form.email, password: form.password })
      // Автоматический вход после регистрации
      const { data } = await login({ email: form.email, password: form.password })
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('user', JSON.stringify(data.user))
      onLogin(data.user)
      navigate('/')
    } catch (e) {
      const detail = e.response?.data?.detail
      setError(Array.isArray(detail)
        ? detail.map(d => d.msg).join(', ')
        : (detail || 'Ошибка регистрации')
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-logo">⚗️ AB Platform</div>
        <h1 className="auth-title">Регистрация</h1>

        {error && <div className="alert alert-danger">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Имя пользователя</label>
            <input required autoFocus placeholder="yourname" minLength={2}
              value={form.username}
              onChange={e => setForm({ ...form, username: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Email</label>
            <input type="email" required placeholder="you@company.com"
              value={form.email}
              onChange={e => setForm({ ...form, email: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Пароль</label>
            <input type="password" required minLength={8} placeholder="Минимум 8 символов"
              value={form.password}
              onChange={e => setForm({ ...form, password: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Подтверждение пароля</label>
            <input type="password" required placeholder="Повторите пароль"
              value={form.confirm}
              onChange={e => setForm({ ...form, confirm: e.target.value })} />
          </div>
          <button type="submit" className="btn btn-primary auth-submit" disabled={loading}>
            {loading ? 'Создание аккаунта...' : 'Создать аккаунт'}
          </button>
        </form>

        <p className="auth-footer">
          Уже есть аккаунт? <Link to="/login">Войти</Link>
        </p>
      </div>
    </div>
  )
}
