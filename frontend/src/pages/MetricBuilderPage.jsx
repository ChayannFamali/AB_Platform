import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { ArrowLeft, Plus, Save } from 'lucide-react'

import {
  createCustomMetric,
  getCustomMetricByKey,
  previewCustomMetric,
  updateCustomMetric,
} from '../api/client'
import PageContainer, { PageHeader } from '../components/PageContainer'
import LoadingState from '../components/LoadingState'
import ErrorBoundary from '../components/ErrorBoundary'
import MetricFilterRow from '../components/metrics/MetricFilterRow'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Alert, AlertDescription } from '../components/ui/alert'
import { Badge } from '../components/ui/badge'
import { toast } from '../hooks/use-toast'

let _localRuleId = 0
const nextRuleId = () => `local-${++_localRuleId}`

function emptyFilter() {
  return {
    id: nextRuleId(),
    field: '',
    operator: 'eq',
    value: '',
    priority: 0,
    enabled: true,
  }
}

const KEY_RE = /^[a-z0-9][a-z0-9_-]*$/

/**
 * Metric builder — handles /custom-metrics/new and /custom-metrics/:key
 * via a `key` prop that forces re-mount when navigating between metrics.
 * Mirrors SegmentBuilderPage so the editing UX is identical for the
 * shared operator vocabulary (9 operators, AND-combined).
 */
export default function MetricBuilderPage() {
  const { key: routeKey } = useParams()
  return <MetricBuilder key={routeKey || 'new'} routeKey={routeKey} />
}

function MetricBuilder({ routeKey }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const isEdit = Boolean(routeKey)

  const { data: existing, isLoading } = useQuery({
    queryKey: ['customMetric', routeKey],
    queryFn: () => getCustomMetricByKey(routeKey),
    enabled: isEdit,
  })

  const [form, setForm] = useState(() => ({
    key: '',
    name: '',
    description: '',
    event_name: '',
    aggregation: 'count',
    metric_type: 'conversion',
    denominator_event_name: '',
    denominator_aggregation: 'count',
    is_guardrail: false,
  }))
  const [filters, setFilters] = useState(() => {
    if (existing?.filters?.length) {
      return existing.filters.map((r) => ({ ...r, id: nextRuleId() }))
    }
    return [emptyFilter()]
  })

  const [hydratedFrom, setHydratedFrom] = useState(existing?.id ?? null)
  if (isEdit && existing && hydratedFrom !== existing.id) {
    setForm({
      key: existing.key,
      name: existing.name,
      description: existing.description || '',
      event_name: existing.event_name,
      aggregation: existing.aggregation,
      metric_type: existing.metric_type,
      denominator_event_name: existing.denominator_event_name || '',
      denominator_aggregation: existing.denominator_aggregation || 'count',
      is_guardrail: existing.is_guardrail,
    })
    setFilters(
      existing.filters?.length
        ? existing.filters.map((r) => ({ ...r, id: nextRuleId() }))
        : [emptyFilter()],
    )
    setHydratedFrom(existing.id)
  }

  const [previewProps, setPreviewProps] = useState('{\n  "country": "DE"\n}')
  const [previewResult, setPreviewResult] = useState(null)

  const previewMutation = useMutation({
    mutationFn: async () => {
      let parsed
      try {
        parsed = JSON.parse(previewProps || '{}')
      } catch {
        throw new Error(t('customMetrics.previewInvalidJson'))
      }
      return previewCustomMetric(existing.id, parsed)
    },
    onSuccess: (data) => setPreviewResult({ ok: true, data }),
    onError: (err) => setPreviewResult({ ok: false, error: err.message }),
  })

  const buildFiltersPayload = () =>
    filters
      .filter((f) => f.field)
      .map((f) => {
        const { id: _ignored, ...rest } = f
        return rest
      })

  const createMutation = useMutation({
    mutationFn: () => createCustomMetric({
      ...form,
      filters: buildFiltersPayload(),
      denominator_event_name: form.denominator_event_name || null,
      denominator_aggregation: form.denominator_event_name
        ? form.denominator_aggregation : null,
    }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['customMetrics'] })
      toast({ description: t('customMetrics.created') })
      navigate(`/custom-metrics/${encodeURIComponent(data.key)}`)
    },
    onError: (err) => toast({
      variant: 'destructive',
      description: err.response?.data?.detail || t('errors.serverError'),
    }),
  })

  const updateMutation = useMutation({
    mutationFn: () => updateCustomMetric(existing.id, {
      name: form.name,
      description: form.description,
      filters: buildFiltersPayload(),
      denominator_event_name: form.denominator_event_name || null,
      denominator_aggregation: form.denominator_event_name
        ? form.denominator_aggregation : null,
      is_guardrail: form.is_guardrail,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customMetrics'] })
      queryClient.invalidateQueries({ queryKey: ['customMetric', routeKey] })
      toast({ description: t('customMetrics.updated') })
    },
    onError: (err) => toast({
      variant: 'destructive',
      description: err.response?.data?.detail || t('errors.serverError'),
    }),
  })

  const keyError = form.key && !KEY_RE.test(form.key)
    ? t('flags.errors.keyFormat') : null
  const saveDisabled =
    createMutation.isPending
    || updateMutation.isPending
    || !form.name
    || !form.event_name
    || (!isEdit && (!form.key || !!keyError))

  const onSave = () => {
    if (isEdit) updateMutation.mutate()
    else createMutation.mutate()
  }

  const isRatio = form.metric_type !== 'conversion' && !!form.denominator_event_name

  return (
    <PageContainer>
      <PageHeader
        title={isEdit ? t('customMetrics.editTitle') : t('customMetrics.new')}
        actions={
          <div className="flex gap-2">
            <Button asChild variant="ghost" size="sm">
              <Link to="/custom-metrics">
                <ArrowLeft className="mr-1 h-4 w-4" />
                {t('common.back')}
              </Link>
            </Button>
            <Button onClick={onSave} disabled={saveDisabled}>
              <Save className="mr-1 h-4 w-4" />
              {t('common.save')}
            </Button>
          </div>
        }
      />

      <ErrorBoundary>
        {isEdit && isLoading ? (
          <LoadingState />
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">
                    {t('customMetrics.configCard')}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="space-y-1">
                    <Label htmlFor="cm-key">{t('customMetrics.keyLabel')}</Label>
                    <Input
                      id="cm-key"
                      value={form.key}
                      onChange={(e) => setForm({ ...form, key: e.target.value })}
                      disabled={isEdit}
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
                    <Label htmlFor="cm-desc">{t('customMetrics.description')}</Label>
                    <Input
                      id="cm-desc"
                      value={form.description}
                      onChange={(e) => setForm({ ...form, description: e.target.value })}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="cm-event">{t('customMetrics.eventNameLabel')}</Label>
                    <Input
                      id="cm-event"
                      value={form.event_name}
                      onChange={(e) => setForm({ ...form, event_name: e.target.value })}
                      placeholder={t('customMetrics.eventNamePlaceholder')}
                      disabled={isEdit}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <Label htmlFor="cm-agg">
                        {t('customMetrics.aggregationLabel')}
                      </Label>
                      <select
                        id="cm-agg"
                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                        value={form.aggregation}
                        onChange={(e) => setForm({ ...form, aggregation: e.target.value })}
                        disabled={isEdit}
                      >
                        <option value="count">{t('customMetrics.agg_count')}</option>
                        <option value="sum">{t('customMetrics.agg_sum')}</option>
                        <option value="avg">{t('customMetrics.agg_avg')}</option>
                        <option value="unique_count">{t('customMetrics.agg_unique_count')}</option>
                      </select>
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="cm-type">
                        {t('customMetrics.metricTypeLabel')}
                      </Label>
                      <select
                        id="cm-type"
                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                        value={form.metric_type}
                        onChange={(e) => setForm({ ...form, metric_type: e.target.value })}
                        disabled={isEdit}
                      >
                        <option value="conversion">{t('customMetrics.type_conversion')}</option>
                        <option value="revenue">{t('customMetrics.type_revenue')}</option>
                        <option value="duration">{t('customMetrics.type_duration')}</option>
                      </select>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="cm-denom">
                      {t('customMetrics.denominatorEventLabel')}
                    </Label>
                    <Input
                      id="cm-denom"
                      value={form.denominator_event_name}
                      onChange={(e) => setForm({ ...form, denominator_event_name: e.target.value })}
                      placeholder="session_start"
                      disabled={isEdit || form.metric_type === 'conversion'}
                    />
                  </div>
                  {isRatio && (
                    <div className="space-y-1">
                      <Label htmlFor="cm-denom-agg">
                        {t('customMetrics.denominatorAggregationLabel')}
                      </Label>
                      <select
                        id="cm-denom-agg"
                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                        value={form.denominator_aggregation}
                        onChange={(e) => setForm({ ...form, denominator_aggregation: e.target.value })}
                      >
                        <option value="count">{t('customMetrics.agg_count')}</option>
                        <option value="sum">{t('customMetrics.agg_sum')}</option>
                        <option value="avg">{t('customMetrics.agg_avg')}</option>
                      </select>
                    </div>
                  )}
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={form.is_guardrail}
                      onChange={(e) => setForm({ ...form, is_guardrail: e.target.checked })}
                    />
                    {t('customMetrics.isGuardrail')}
                  </label>
                  <p className="text-xs text-muted-foreground">
                    {t('customMetrics.isGuardrailHelp')}
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">
                    {t('customMetrics.filtersCard')}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {filters.map((r) => (
                    <MetricFilterRow
                      key={r.id}
                      rule={r}
                      onChange={(next) =>
                        setFilters(filters.map((x) => (x.id === r.id ? next : x)))
                      }
                      onRemove={() => setFilters(filters.filter((x) => x.id !== r.id))}
                    />
                  ))}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setFilters([...filters, emptyFilter()])}
                  >
                    <Plus className="mr-1 h-4 w-4" />
                    {t('customMetrics.filterAdd')}
                  </Button>
                </CardContent>
              </Card>
            </div>

            {isEdit && existing ? (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">
                    {t('customMetrics.previewCard')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <Alert className="mb-3">
                    <AlertDescription>
                      {t('customMetrics.previewHelp')}
                    </AlertDescription>
                  </Alert>
                  <div className="space-y-3">
                    <div className="space-y-1">
                      <Label htmlFor="preview-props">
                        {t('customMetrics.previewPropsLabel')}
                      </Label>
                      <textarea
                        id="preview-props"
                        className="flex min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
                        rows={5}
                        value={previewProps}
                        onChange={(e) => setPreviewProps(e.target.value)}
                      />
                    </div>
                    <Button
                      size="sm"
                      onClick={() => previewMutation.mutate()}
                      disabled={previewMutation.isPending}
                    >
                      {t('customMetrics.previewRun')}
                    </Button>
                    {previewResult?.ok && (
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-medium">
                            {t('customMetrics.previewResult')}:
                          </span>
                          {previewResult.data.matches ? (
                            <Badge variant="success">
                              {t('customMetrics.previewMatches')}
                            </Badge>
                          ) : (
                            <Badge variant="destructive">
                              {t('customMetrics.previewNoMatch')}
                            </Badge>
                          )}
                          <span className="text-xs text-muted-foreground">
                            {t('customMetrics.previewMatchedCount', {
                              matched: previewResult.data.matched_filters,
                              total: previewResult.data.total_filters,
                            })}
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {previewResult.data.summary}
                        </p>
                        <ul className="divide-y rounded border text-xs">
                          {(previewResult.data.per_filter || []).map((r, i) => (
                            <li
                              key={i}
                              className="flex items-center justify-between px-3 py-1.5"
                            >
                              <span className="font-mono">
                                {r.field} {r.operator} {JSON.stringify(r.expected)}
                              </span>
                              {r.matched ? (
                                <Badge variant="secondary">
                                  {t('customMetrics.previewRuleMatch')}
                                </Badge>
                              ) : (
                                <Badge variant="outline">
                                  {t('customMetrics.previewRuleNoMatch')}
                                </Badge>
                              )}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {previewResult && !previewResult.ok && (
                      <Alert variant="destructive">
                        <AlertDescription>{previewResult.error}</AlertDescription>
                      </Alert>
                    )}
                  </div>
                </CardContent>
              </Card>
            ) : (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">
                    {t('customMetrics.previewCard')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <Alert>
                    <AlertDescription>
                      {t('segments.previewSaveFirst')}
                    </AlertDescription>
                  </Alert>
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </ErrorBoundary>
    </PageContainer>
  )
}
