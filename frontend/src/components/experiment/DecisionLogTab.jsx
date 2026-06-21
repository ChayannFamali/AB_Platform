import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { ClipboardList, Plus } from 'lucide-react'

import { addDecision, getDecisions } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'
import DecisionForm from './DecisionForm'
import EmptyState from '../EmptyState'
import ErrorBoundary from '../ErrorBoundary'
import LoadingState from '../LoadingState'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { Card, CardContent } from '../ui/card'
import { toast } from '../../hooks/use-toast'

const STATUS_VARIANT = {
  ship: 'success',
  stop: 'destructive',
  iterate: 'warning',
  inconclusive: 'secondary',
}

/**
 * Per-experiment decision log tab. Shows the chronological list of
 * decisions (newest first) and provides a modal form for appending a
 * new decision. The form is hidden for users without
 * `decisions:write` (analyst / viewer) — see the `canWrite` selector.
 *
 * The log is intentionally append-only: there is no edit / delete UI
 * surface. Corrections are made by recording a new decision.
 */
export default function DecisionLogTab({ experimentId }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [formOpen, setFormOpen] = useState(false)
  const user = useAuthStore((s) => s.user)
  const permissions = Array.isArray(user?.permissions) ? user.permissions : []
  const canWrite = permissions.includes('decisions:write')

  const { data, isLoading } = useQuery({
    queryKey: ['decisions', experimentId],
    queryFn: () => getDecisions(experimentId, { limit: 100 }),
    enabled: Boolean(experimentId),
  })

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['decisions', experimentId] })

  const createMutation = useMutation({
    mutationFn: (body) => addDecision(experimentId, body),
    onSuccess: () => {
      invalidate()
      // The latest decision may have flipped `experiment.decision_status`,
      // which ExperimentDetailPage renders in the page header. Refetch
      // the experiment so the badge stays in sync.
      queryClient.invalidateQueries({ queryKey: ['experiment', experimentId] })
      setFormOpen(false)
      toast({ description: t('decisions.recorded') })
    },
    onError: (err) =>
      toast({
        variant: 'destructive',
        description: err.response?.data?.detail || t('errors.serverError'),
      }),
  })

  const items = data?.items || []

  return (
    <ErrorBoundary>
      <div className="mb-4 flex items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          {t('decisions.subtitle')}
        </p>
        {canWrite && (
          <Button
            size="sm"
            onClick={() => setFormOpen(true)}
            disabled={!experimentId}
          >
            <Plus className="mr-1 h-4 w-4" />
            {t('decisions.add')}
          </Button>
        )}
      </div>

      {isLoading ? (
        <LoadingState />
      ) : items.length === 0 ? (
        <EmptyState
          icon={ClipboardList}
          title={t('decisions.empty')}
          description={canWrite ? t('decisions.emptyWrite') : t('decisions.emptyRead')}
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <ul className="divide-y">
              {items.map((d) => (
                <li key={d.id} className="px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <Badge variant={STATUS_VARIANT[d.status] || 'secondary'}>
                        {t(`decisions.${d.status}`)}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {t('decisions.by', {
                          username: d.decided_by_username || '—',
                        })}
                      </span>
                    </div>
                    <time className="text-xs text-muted-foreground">
                      {new Date(d.decided_at).toLocaleString()}
                    </time>
                  </div>
                  {d.comment && (
                    <p className="mt-2 whitespace-pre-wrap text-sm text-foreground">
                      {d.comment}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <DecisionForm
        open={formOpen}
        onOpenChange={setFormOpen}
        onSubmit={(body) => createMutation.mutate(body)}
        submitting={createMutation.isPending}
      />
    </ErrorBoundary>
  )
}