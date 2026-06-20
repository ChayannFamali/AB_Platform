import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Beaker, ClipboardList, Flag, FlaskConical, ScrollText } from 'lucide-react'

import { getAuditLog, getExperiments, getFlagSummary } from '../api/client'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import LoadingState from '../components/LoadingState'
import { PageHeader } from '../components/PageContainer'

const ACTION_VARIANT = {
  create:         'success',
  update:         'info',
  delete:         'destructive',
  assign:         'success',
  revoke:         'warning',
  toggle_active:  'secondary',
  toggle_enabled: 'secondary',
  add_rule:       'info',
  delete_rule:    'info',
}

const RESOURCE_VARIANT = {
  role:         'default',
  user:         'info',
  user_role:    'secondary',
  feature_flag: 'warning',
}

export default function DashboardPage() {
  const { t, i18n } = useTranslation()

  const experimentsQuery = useQuery({
    queryKey: ['experiments', { limit: 100, offset: 0 }],
    queryFn: () =>
      getExperiments({ limit: 100, offset: 0 }).then((r) => r.data),
  })

  const auditQuery = useQuery({
    queryKey: ['audit', { limit: 5, offset: 0 }],
    queryFn: () =>
      getAuditLog({ limit: 5, offset: 0 }).then((r) => r.data),
  })

  const flagsQuery = useQuery({
    queryKey: ['flagSummary'],
    queryFn: () => getFlagSummary(),
  })

  const experiments = experimentsQuery.data?.items ?? []
  const total = experimentsQuery.data?.total ?? 0
  const runningCount = experiments.filter((e) => e.status === 'running').length
  const completedNoDecisionCount = experiments.filter(
    (e) => e.status === 'completed',
  ).length

  const auditItems = auditQuery.data?.items ?? []
  const locale = i18n.language === 'en' ? 'en-US' : 'ru-RU'

  return (
    <>
      <PageHeader title={t('dashboard.title')} />

      {experimentsQuery.isLoading ? (
        <LoadingState variant="skeleton" count={3} />
      ) : (
        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <SummaryCard
            icon={FlaskConical}
            label={t('dashboard.running')}
            value={runningCount}
            loading={experimentsQuery.isLoading}
          />
          <SummaryCard
            icon={ClipboardList}
            label={t('dashboard.pendingDecisions')}
            value={completedNoDecisionCount}
            loading={experimentsQuery.isLoading}
          />
          <SummaryCard
            icon={Beaker}
            label={t('dashboard.totalExperiments')}
            value={total}
            loading={experimentsQuery.isLoading}
          />
          <SummaryCard
            icon={Flag}
            label={t('dashboard.activeFlags')}
            value={flagsQuery.data?.enabled_with_rollout ?? 0}
            loading={flagsQuery.isLoading}
          />
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <ScrollText className="h-4 w-4" />
              {t('dashboard.recentActivity')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {auditQuery.isLoading ? (
              <LoadingState variant="skeleton" count={3} />
            ) : auditItems.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {t('dashboard.noActivity')}
              </p>
            ) : (
              <ul className="divide-y">
                {auditItems.map((entry) => (
                  <li
                    key={entry.id}
                    className="flex items-center gap-3 py-2 text-sm"
                  >
                    <span className="text-muted-foreground">
                      {new Date(entry.created_at).toLocaleString(locale)}
                    </span>
                    <span className="font-medium">
                      {entry.user_username || (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </span>
                    <Badge variant={ACTION_VARIANT[entry.action] || 'secondary'}>
                      {t(`audit.action_${entry.action}`, {
                        defaultValue: entry.action,
                      })}
                    </Badge>
                    <Badge
                      variant={RESOURCE_VARIANT[entry.resource_type] || 'outline'}
                    >
                      {t(`audit.resourceType_${entry.resource_type}`, {
                        defaultValue: entry.resource_type,
                      })}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-3 flex justify-end">
              <Button asChild variant="ghost" size="sm">
                <Link to="/settings/audit">{t('dashboard.viewAll')}</Link>
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">{t('dashboard.quickActions')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Button asChild className="w-full justify-start">
              <Link to="/experiments/new">
                {t('dashboard.newExperiment')}
              </Link>
            </Button>
            <Button asChild variant="outline" className="w-full justify-start">
              <Link to="/api-keys">{t('dashboard.newApiKey')}</Link>
            </Button>
            <Button asChild variant="outline" className="w-full justify-start">
              <Link to="/settings/audit">{t('dashboard.viewAudit')}</Link>
            </Button>
            <Button asChild variant="outline" className="w-full justify-start">
              <Link to="/settings/users">{t('dashboard.manageUsers')}</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    </>
  )
}

function SummaryCard({ icon: Icon, label, value, loading, hint, disabled }) {
  return (
    <Card className={disabled ? 'opacity-60' : ''}>
      <CardContent className="flex items-start justify-between p-4">
        <div>
          <div className="text-xs text-muted-foreground">{label}</div>
          {loading ? (
            <div className="mt-1 h-7 w-12 animate-pulse rounded bg-muted" />
          ) : (
            <div className="mt-1 text-2xl font-semibold">{value}</div>
          )}
          {hint && (
            <div className="mt-1 text-xs text-muted-foreground">{hint}</div>
          )}
        </div>
        {Icon && (
          <Icon className="h-5 w-5 text-muted-foreground" aria-hidden />
        )}
      </CardContent>
    </Card>
  )
}
