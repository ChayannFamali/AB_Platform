import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Plus, Ruler, Trash2 } from 'lucide-react'

import {
  createCustomMetric,
  deleteCustomMetric,
  getCustomMetrics,
} from '../api/client'
import PageContainer, { PageHeader } from '../components/PageContainer'
import EmptyState from '../components/EmptyState'
import LoadingState from '../components/LoadingState'
import ErrorBoundary from '../components/ErrorBoundary'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import { Card, CardContent } from '../components/ui/card'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from '../components/ui/dialog'
import { toast } from '../hooks/use-toast'

const KEY_RE = /^[a-z0-9][a-z0-9_-]*$/

export default function CustomMetricListPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [form, setForm] = useState({
    key: '',
    name: '',
    description: '',
    event_name: '',
    aggregation: 'count',
    metric_type: 'conversion',
  })
  const [pendingDelete, setPendingDelete] = useState(null)

  const { data, isLoading } = useQuery({
    queryKey: ['customMetrics'],
    queryFn: () => getCustomMetrics({ limit: 100 }),
  })

  const createMutation = useMutation({
    mutationFn: () => createCustomMetric({ ...form, filters: [] }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customMetrics'] })
      setCreateOpen(false)
      setForm({
        key: '', name: '', description: '',
        event_name: '', aggregation: 'count', metric_type: 'conversion',
      })
      toast({ description: t('customMetrics.created') })
    },
    onError: (err) => toast({
      variant: 'destructive',
      description: err.response?.data?.detail || t('errors.serverError'),
    }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => deleteCustomMetric(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customMetrics'] })
      setPendingDelete(null)
      toast({ description: t('customMetrics.deleted') })
    },
    onError: (err) => toast({
      variant: 'destructive',
      description: err.response?.data?.detail || t('errors.serverError'),
    }),
  })

  const items = data?.items || []
  const keyError = form.key && !KEY_RE.test(form.key)
    ? t('flags.errors.keyFormat') : null

  return (
    <PageContainer>
      <PageHeader
        title={t('customMetrics.title')}
        subtitle={t('customMetrics.subtitle')}
        actions={
          <Button asChild>
            <Link to="/custom-metrics/new">
              <Plus className="mr-1 h-4 w-4" />
              {t('customMetrics.new')}
            </Link>
          </Button>
        }
      />

      <ErrorBoundary>
        {isLoading ? (
          <LoadingState />
        ) : items.length === 0 ? (
          <EmptyState
            icon={<Ruler className="h-10 w-10" />}
            title={t('customMetrics.empty')}
            description={t('customMetrics.emptyDescription')}
          />
        ) : (
          <Card>
            <CardContent className="p-0">
              <ul className="divide-y">
                {items.map((m) => (
                  <li
                    key={m.id}
                    className="flex items-center justify-between gap-3 px-4 py-3"
                  >
                    <div className="min-w-0 flex-1">
                      <Link
                        to={`/custom-metrics/${encodeURIComponent(m.key)}`}
                        className="font-medium hover:underline"
                      >
                        {m.name}
                      </Link>
                      <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        <code className="rounded bg-muted px-1.5 py-0.5">
                          {m.key}
                        </code>
                        <span>·</span>
                        <Badge variant="outline">
                          {t(`customMetrics.agg_${m.aggregation}`)}
                        </Badge>
                        <Badge variant="secondary">
                          {t(`customMetrics.type_${m.metric_type}`)}
                        </Badge>
                        <span>·</span>
                        <span>
                          {m.used_by_count > 0
                            ? t('customMetrics.usedBy', { count: m.used_by_count })
                            : t('customMetrics.usedByNone')}
                        </span>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setPendingDelete(m)}
                      aria-label={t('common.delete')}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}
      </ErrorBoundary>

      {/* Create dialog — minimal; the full builder lives at /custom-metrics/new */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('customMetrics.new')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <Label htmlFor="cm-key">{t('customMetrics.keyLabel')}</Label>
              <Input
                id="cm-key"
                value={form.key}
                onChange={(e) => setForm({ ...form, key: e.target.value })}
                placeholder="eu_purchases"
                aria-invalid={!!keyError}
              />
              {keyError && (
                <p className="text-xs text-destructive">{keyError}</p>
              )}
            </div>
            <div className="space-y-1">
              <Label htmlFor="cm-name">{t('customMetrics.nameLabel')}</Label>
              <Input
                id="cm-name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder={t('customMetrics.namePlaceholder')}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="cm-event">{t('customMetrics.eventNameLabel')}</Label>
              <Input
                id="cm-event"
                value={form.event_name}
                onChange={(e) => setForm({ ...form, event_name: e.target.value })}
                placeholder={t('customMetrics.eventNamePlaceholder')}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="cm-agg">{t('customMetrics.aggregationLabel')}</Label>
                <select
                  id="cm-agg"
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={form.aggregation}
                  onChange={(e) => setForm({ ...form, aggregation: e.target.value })}
                >
                  <option value="count">{t('customMetrics.agg_count')}</option>
                  <option value="sum">{t('customMetrics.agg_sum')}</option>
                  <option value="avg">{t('customMetrics.agg_avg')}</option>
                  <option value="unique_count">{t('customMetrics.agg_unique_count')}</option>
                </select>
              </div>
              <div className="space-y-1">
                <Label htmlFor="cm-type">{t('customMetrics.metricTypeLabel')}</Label>
                <select
                  id="cm-type"
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={form.metric_type}
                  onChange={(e) => setForm({ ...form, metric_type: e.target.value })}
                >
                  <option value="conversion">{t('customMetrics.type_conversion')}</option>
                  <option value="revenue">{t('customMetrics.type_revenue')}</option>
                  <option value="duration">{t('customMetrics.type_duration')}</option>
                </select>
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              {t('customMetrics.emptyDescription')}
            </p>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              onClick={() => createMutation.mutate()}
              disabled={
                createMutation.isPending
                || !form.key
                || !form.name
                || !form.event_name
                || !!keyError
              }
            >
              {t('common.create')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={!!pendingDelete}
        onOpenChange={(open) => !open && setPendingDelete(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('customMetrics.delete')}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {t('customMetrics.deleteConfirm', { name: pendingDelete?.name })}
          </p>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setPendingDelete(null)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteMutation.mutate(pendingDelete.id)}
              disabled={deleteMutation.isPending}
            >
              {t('common.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageContainer>
  )
}
