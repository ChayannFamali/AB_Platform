import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ChevronRight, Languages, Moon, Shield, ScrollText, Users } from 'lucide-react'

import { useAuthStore } from '../stores/authStore'
import { useUiStore } from '../stores/uiStore'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Label } from '../components/ui/label'
import { PageHeader } from '../components/PageContainer'

export default function SettingsPage() {
  const { t, i18n } = useTranslation()
  const user = useAuthStore((s) => s.user)
  const roles = useAuthStore((s) => s.roles)
  const theme = useUiStore((s) => s.theme)
  const toggleTheme = useUiStore((s) => s.toggleTheme)
  const setLocale = useUiStore((s) => s.setLocale)
  const isAdmin = Array.isArray(roles) && roles.includes('admin')

  return (
    <>
      <PageHeader
        title={t('settings.title')}
        description={t('settings.subtitle')}
      />

      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Languages className="h-4 w-4" />
              {t('settings.language')}
            </CardTitle>
            <CardDescription>{t('settings.languageHint')}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <Button
                variant={i18n.language === 'ru' ? 'default' : 'outline'}
                onClick={() => setLocale('ru')}
                size="sm"
              >
                Русский
              </Button>
              <Button
                variant={i18n.language === 'en' ? 'default' : 'outline'}
                onClick={() => setLocale('en')}
                size="sm"
              >
                English
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Moon className="h-4 w-4" />
              {t('settings.theme')}
            </CardTitle>
            <CardDescription>{t('settings.themeHint')}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <Label>{t('settings.currentTheme')}</Label>
              <Button variant="outline" size="sm" onClick={toggleTheme}>
                {theme === 'dark'
                  ? t('common.lightMode')
                  : t('common.darkMode')}
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {t('settings.adminSection')}
            </CardTitle>
            <CardDescription>{t('settings.adminHint')}</CardDescription>
          </CardHeader>
          <CardContent className="divide-y">
            <SettingsLink
              to="/settings/audit"
              icon={ScrollText}
              title={t('audit.title')}
              description={t('audit.subtitle')}
            />
            {isAdmin && (
              <SettingsLink
                to="/settings/users"
                icon={Users}
                title={t('users.title')}
                description={t('users.subtitle')}
              />
            )}
            <SettingsLink
              to="/api-keys"
              icon={Shield}
              title={t('apiKeys.title')}
              description={t('settings.apiKeysHint')}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t('settings.about')}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">
                {t('settings.version')}
              </span>
              <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                {t('settings.versionValue')}
              </code>
            </div>
            {user?.username && (
              <div className="mt-2 flex items-center justify-between">
                <span className="text-muted-foreground">
                  {t('auth.loggedInAs')}
                </span>
                <span className="font-medium">{user.username}</span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  )
}

function SettingsLink({ to, icon: Icon, title, description }) {
  return (
    <Link
      to={to}
      className="flex items-center gap-3 py-3 transition-colors hover:bg-muted/40"
    >
      {Icon && <Icon className="h-4 w-4 text-muted-foreground" />}
      <div className="flex-1">
        <div className="text-sm font-medium">{title}</div>
        <div className="text-xs text-muted-foreground">{description}</div>
      </div>
      <ChevronRight className="h-4 w-4 text-muted-foreground" />
    </Link>
  )
}
