import { useTranslation } from 'react-i18next'

import { Badge } from '../ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'

const STATUS_VARIANT = {
  draft:     'secondary',
  running:   'success',
  paused:    'warning',
  completed: 'info',
}

export default function ExperimentStatusCard({ experiment }) {
  const { t, i18n } = useTranslation()

  if (!experiment) return null

  const locale = i18n.language === 'en' ? 'en-US' : 'ru-RU'
  const fmt = (iso) => (iso ? new Date(iso).toLocaleString(locale) : '—')

  const metrics = [
    {
      label: t('experiments.create.status'),
      value: (
        <Badge variant={STATUS_VARIANT[experiment.status] || 'secondary'}>
          {t(`experiments.list.${experiment.status}`)}
        </Badge>
      ),
    },
    {
      label: t('experiments.list.traffic'),
      value: `${experiment.traffic_percentage}%`,
    },
    {
      label: t('experiments.create.variants'),
      value: experiment.variants?.length ?? 0,
    },
    {
      label: t('experiments.create.metrics'),
      value: experiment.metrics?.length ?? 0,
    },
    {
      label: t('experiments.detail.startedAt'),
      value: fmt(experiment.started_at),
    },
    {
      label: t('experiments.detail.endedAt'),
      value: fmt(experiment.ended_at),
    },
  ]

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="text-base">
          {t('experiments.detail.summary')}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          {metrics.map((m) => (
            <div key={m.label} className="text-sm">
              <dt className="text-xs text-muted-foreground">{m.label}</dt>
              <dd className="mt-1 font-medium">{m.value}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  )
}
