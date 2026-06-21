import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { ArrowLeft, Plus, Save } from 'lucide-react'

import {
  createSegment,
  getSegmentByKey,
  updateSegment,
} from '../api/client'
import PageContainer from '../components/PageContainer'
import LoadingState from '../components/LoadingState'
import ErrorBoundary from '../components/ErrorBoundary'
import SegmentRuleRow from '../components/segments/SegmentRuleRow'
import SegmentPreview from '../components/segments/SegmentPreview'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Alert, AlertDescription } from '../components/ui/alert'
import { toast } from '../hooks/use-toast'

let _localRuleId = 0
const nextRuleId = () => `local-${++_localRuleId}`

function emptyRule() {
  return { id: nextRuleId(), field: '', operator: 'eq', value: '', priority: 0, enabled: true }
}

const KEY_RE = /^[a-z0-9][a-z0-9_-]*$/

/**
 * Segment builder — handles /segments/new and /segments/:key via a
 * `key` prop that forces re-mount when navigating between segments.
 * The inner `_SegmentBuilder` only sees one segment per mount, so its
 * local state can be initialised from props without effects.
 */
export default function SegmentBuilderPage() {
  const { key: routeKey } = useParams()
  return <SegmentBuilder key={routeKey || 'new'} routeKey={routeKey} />
}

function SegmentBuilder({ routeKey }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const isEdit = Boolean(routeKey)

  // For edit mode, we load the existing segment synchronously into
  // local state via `useState`'s lazy initializer — no useEffect needed.
  const { data: existing, isLoading } = useQuery({
    queryKey: ['segment', routeKey],
    queryFn: () => getSegmentByKey(routeKey),
    enabled: isEdit,
  })

  const [form, setForm] = useState(() => ({
    key: '',
    name: '',
    description: '',
  }))
  const [rules, setRules] = useState(() => {
    if (existing?.rules?.length) {
      return existing.rules.map((r) => ({ ...r, id: nextRuleId() }))
    }
    return [emptyRule()]
  })

  // When the existing query resolves (or when we navigate to a new
  // segment via `key` remount), update form/rules from the loaded
  // data — but only once, identified by `existing.id`.
  const [hydratedFrom, setHydratedFrom] = useState(existing?.id ?? null)
  if (isEdit && existing && hydratedFrom !== existing.id) {
    setForm({
      key: existing.key,
      name: existing.name,
      description: existing.description || '',
    })
    setRules(
      existing.rules?.length
        ? existing.rules.map((r) => ({ ...r, id: nextRuleId() }))
        : [emptyRule()],
    )
    setHydratedFrom(existing.id)
  }

  const createMutation = useMutation({
    mutationFn: () => createSegment({
      ...form,
      rules: rules
        .filter((r) => r.field)
        .map((r) => {
          const { id: _ignored, ...rest } = r
          return rest
        }),
    }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['segments'] })
      toast({ description: t('segments.created') })
      navigate(`/segments/${encodeURIComponent(data.key)}`)
    },
    onError: (err) => toast({
      variant: 'destructive',
      description: err.response?.data?.detail || t('errors.serverError'),
    }),
  })

  const updateMutation = useMutation({
    mutationFn: () => updateSegment(existing.id, {
      name: form.name,
      description: form.description,
      rules: rules
        .filter((r) => r.field)
        .map((r) => {
          const { id: _ignored, ...rest } = r
          return rest
        }),
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['segments'] })
      queryClient.invalidateQueries({ queryKey: ['segment', routeKey] })
      toast({ description: t('segments.updated') })
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
    || (!isEdit && (!form.key || !!keyError))
    || rules.every((r) => !r.field)

  const onSave = () => {
    if (isEdit) updateMutation.mutate()
    else createMutation.mutate()
  }

  return (
    <PageContainer
      title={isEdit ? t('segments.editTitle') : t('segments.new')}
      actions={
        <div className="flex gap-2">
          <Button asChild variant="ghost" size="sm">
            <Link to="/segments"><ArrowLeft className="mr-1 h-4 w-4" />{t('common.back')}</Link>
          </Button>
          <Button onClick={onSave} disabled={saveDisabled}>
            <Save className="mr-1 h-4 w-4" />
            {t('common.save')}
          </Button>
        </div>
      }
    >
      <ErrorBoundary>
        {isEdit && isLoading ? (
          <LoadingState />
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">{t('segments.configCard')}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="space-y-1">
                    <Label htmlFor="seg-key">{t('segments.keyLabel')}</Label>
                    <Input
                      id="seg-key"
                      value={form.key}
                      onChange={(e) => setForm({ ...form, key: e.target.value })}
                      disabled={isEdit}
                      placeholder="eu_users"
                      aria-invalid={!!keyError}
                    />
                    {keyError && (
                      <p className="text-xs text-destructive">{keyError}</p>
                    )}
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="seg-name">{t('segments.nameLabel')}</Label>
                    <Input
                      id="seg-name"
                      value={form.name}
                      onChange={(e) => setForm({ ...form, name: e.target.value })}
                      placeholder={t('segments.namePlaceholder')}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="seg-desc">{t('segments.description')}</Label>
                    <Input
                      id="seg-desc"
                      value={form.description}
                      onChange={(e) => setForm({ ...form, description: e.target.value })}
                    />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">{t('segments.rulesCard')}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {rules.map((r) => (
                    <SegmentRuleRow
                      key={r.id}
                      rule={r}
                      onChange={(next) => setRules(rules.map((x) => (x.id === r.id ? next : x)))}
                      onRemove={() => setRules(rules.filter((x) => x.id !== r.id))}
                    />
                  ))}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setRules([...rules, emptyRule()])}
                  >
                    <Plus className="mr-1 h-4 w-4" />
                    {t('segments.ruleAdd')}
                  </Button>
                </CardContent>
              </Card>
            </div>

            {isEdit && existing ? (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">{t('segments.previewCard')}</CardTitle>
                </CardHeader>
                <CardContent>
                  <Alert className="mb-3">
                    <AlertDescription>{t('segments.previewHelp')}</AlertDescription>
                  </Alert>
                  <SegmentPreview segmentId={existing.id} />
                </CardContent>
              </Card>
            ) : (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">{t('segments.previewCard')}</CardTitle>
                </CardHeader>
                <CardContent>
                  <Alert>
                    <AlertDescription>{t('segments.previewSaveFirst')}</AlertDescription>
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
