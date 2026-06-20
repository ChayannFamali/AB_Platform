import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { login, register } from '../api/client'
import { useAuthStore } from '../stores/authStore'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import { Alert, AlertDescription } from '../components/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'

export default function RegisterPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)

  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    confirm: '',
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (form.password !== form.confirm) {
      setError(t('auth.passwordsDoNotMatch', { defaultValue: 'Passwords do not match' }))
      return
    }

    setLoading(true)
    try {
      await register({
        username: form.username,
        email: form.email,
        password: form.password,
      })
      const { data } = await login({ email: form.email, password: form.password })
      const roles = Array.isArray(data?.user?.roles) ? data.user.roles : []
      setAuth(data.user, data.access_token, roles)
      navigate('/')
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(
        Array.isArray(detail)
          ? detail.map((d) => d.msg).join(', ')
          : detail || t('auth.registerFailed')
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-8">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <div className="text-center text-xl font-bold">
            {t('common.appName')}
          </div>
          <CardTitle className="text-center text-lg">
            {t('auth.registerTitle')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">{t('auth.username')}</Label>
              <Input
                id="username"
                required
                autoFocus
                minLength={2}
                placeholder={t('auth.usernamePlaceholder')}
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">{t('auth.email')}</Label>
              <Input
                id="email"
                type="email"
                required
                placeholder={t('auth.emailPlaceholder')}
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">{t('auth.password')}</Label>
              <Input
                id="password"
                type="password"
                required
                minLength={8}
                placeholder={t('auth.passwordPlaceholder')}
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm">{t('auth.passwordConfirm', { defaultValue: 'Confirm password' })}</Label>
              <Input
                id="confirm"
                type="password"
                required
                placeholder={t('auth.passwordPlaceholder')}
                value={form.confirm}
                onChange={(e) => setForm({ ...form, confirm: e.target.value })}
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? t('common.loading') : t('auth.registerButton')}
            </Button>
          </form>
          <p className="mt-4 text-center text-sm text-muted-foreground">
            {t('auth.haveAccount')}{' '}
            <Link to="/login" className="text-primary hover:underline">
              {t('auth.loginButton')}
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}