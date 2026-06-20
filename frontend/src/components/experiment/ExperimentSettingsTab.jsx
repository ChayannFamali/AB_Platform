import { useTranslation } from 'react-i18next'

import { Badge } from '../ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'

/**
 * Read-only metadata for the experiment. No mutations in M-005 — edit
 * operations land in later milestones (M-006 wizard, M-010 segments).
 */
export default function ExperimentSettingsTab({ experiment }) {
  const { t, i18n } = useTranslation()
  if (!experiment) return null

  const locale = i18n.language === 'en' ? 'en-US' : 'ru-RU'
  const fmt = (iso) => (iso ? new Date(iso).toLocaleString(locale) : '—')

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {t('experiments.detail.basicInfo')}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <Row label={t('experiments.detail.id')} value={
            <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
              {experiment.id}
            </code>
          } />
          <Row
            label={t('experiments.detail.createdAt')}
            value={fmt(experiment.created_at)}
          />
          <Row
            label={t('experiments.detail.updatedAt')}
            value={fmt(experiment.updated_at)}
          />
          <Row
            label={t('experiments.detail.mutexGroup')}
            value={
              experiment.mutex_group_id ? (
                <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                  {experiment.mutex_group_id}
                </code>
              ) : (
                <span className="text-muted-foreground">—</span>
              )
            }
          />
          <Row
            label={t('experiments.detail.sequential')}
            value={
              experiment.is_sequential ? (
                <Badge variant="info">
                  {t('experiments.detail.sequentialOn')}
                </Badge>
              ) : (
                <span className="text-muted-foreground">
                  {t('experiments.detail.sequentialOff')}
                </span>
              )
            }
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {t('experiments.create.variants')}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {(experiment.variants || []).map((v) => (
            <div
              key={v.id}
              className="flex items-center justify-between rounded border bg-muted/40 px-3 py-2"
            >
              <span className="font-medium">{v.name}</span>
              <span className="text-muted-foreground">
                {t('experiments.create.weight')}: {v.traffic_split}%
              </span>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {t('experiments.create.metrics')}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {(experiment.metrics || []).map((m) => (
            <div
              key={m.id}
              className="rounded border bg-muted/40 px-3 py-2"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium">{m.name}</span>
                <span className="flex items-center gap-1">
                  {m.is_primary && (
                    <Badge variant="success">Primary</Badge>
                  )}
                  {m.is_guardrail && (
                    <Badge variant="warning">Guardrail</Badge>
                  )}
                </span>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {m.metric_type} · event: <code>{m.event_name}</code>
                {m.denominator_event_name && (
                  <> · denom: <code>{m.denominator_event_name}</code></>
                )}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span>{value}</span>
    </div>
  )
}
