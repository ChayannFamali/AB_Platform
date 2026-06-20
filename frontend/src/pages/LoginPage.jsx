import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { login } from '../api/client'
import { useAuthStore } from '../stores/authStore'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import { Alert, AlertDescription } from '../components/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'

export default function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)

  const [form, setForm] = useState({ email: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { data } = await login(form)
      const roles = Array.isArray(data?.user?.roles) ? data.user.roles : []
      setAuth(data.user, data.access_token, roles)
      navigate('/')
    } catch (err) {
      setError(
        err.response?.data?.detail || t('auth.invalidCredentials')
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <div className="text-center text-xl font-bold">
            {t('common.appName')}
          </div>
          <CardTitle className="text-center text-lg">
            {t('auth.loginTitle')}
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
              <Label htmlFor="email">{t('auth.email')}</Label>
              <Input
                id="email"
                type="email"
                required
                autoFocus
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
                placeholder={t('auth.passwordPlaceholder')}
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? t('common.loading') : t('auth.loginButton')}
            </Button>
          </form>
          <p className="mt-4 text-center text-sm text-muted-foreground">
            {t('auth.noAccount')}{' '}
            <Link to="/register" className="text-primary hover:underline">
              {t('auth.registerButton')}
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}