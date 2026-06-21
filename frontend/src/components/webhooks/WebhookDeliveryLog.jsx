import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Activity } from 'lucide-react'

import { getWebhookDeliveries } from '../../api/client'
import EmptyState from '../EmptyState'
import LoadingState from '../LoadingState'
import { Badge } from '../ui/badge'

/**
 * Per-webhook delivery log. Polled lightly because webhook deliveries
 * are rare — no live subscription here. Success/failed filter mirrors
 * the backend query param.
 */
export default function WebhookDeliveryLog({ webhookId }) {
  const { t } = useTranslation()
  const [filter, setFilter] = useState('all')

  const { data, isLoading } = useQuery({
    queryKey: ['webhook-deliveries', webhookId, filter],
    queryFn: () =>
      getWebhookDeliveries(webhookId, {
        limit: 50,
        ...(filter !== 'all' ? { success: filter === 'success' } : {}),
      }),
    enabled: Boolean(webhookId),
  })

  const items = data?.items || []

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm">
        <Activity className="h-4 w-4 text-muted-foreground" />
        <span className="font-medium">{t('webhooks.deliveryLogTitle')}</span>
        <span className="ml-auto flex gap-1">
          {['all', 'success', 'failed'].map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={
                'rounded px-2 py-0.5 text-xs ' +
                (filter === f
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground')
              }
            >
              {t(`webhooks.deliveryFilter.${f}`)}
            </button>
          ))}
        </span>
      </div>

      {isLoading ? (
        <LoadingState />
      ) : items.length === 0 ? (
        <EmptyState
          title={t('webhooks.deliveriesEmpty')}
          description={t('webhooks.deliveriesEmptyHint')}
        />
      ) : (
        <ul className="divide-y rounded border bg-card">
          {items.map((d) => (
            <li key={d.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
              <div className="flex items-center gap-2">
                <Badge variant={d.success ? 'success' : 'destructive'}>
                  {d.success ? t('webhooks.success') : t('webhooks.failed')}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {t(`webhooks.eventNames.${d.event_type}`, d.event_type)}
                </span>
              </div>
              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                <span>{d.status_code ?? '—'}</span>
                <span>{d.duration_ms ?? 0} ms</span>
                <span>attempt #{d.attempt}</span>
                <time>{new Date(d.created_at).toLocaleString()}</time>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}