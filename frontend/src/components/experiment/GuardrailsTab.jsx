import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Pencil, Plus, Trash2 } from 'lucide-react'

import {
  createGuardrail,
  deleteGuardrail,
  getGuardrails,
  updateGuardrail,
} from '../../api/client'
import EmptyState from '../EmptyState'
import ErrorBoundary from '../ErrorBoundary'
import LoadingState from '../LoadingState'
import { Alert, AlertDescription } from '../ui/alert'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { Card, CardContent } from '../ui/card'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from '../ui/dialog'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../ui/select'
import { toast } from '../../hooks/use-toast'

/**
 * Per-experiment guardrail configuration tab. Lists existing
 * GuardrailConfig rows for this experiment and provides a modal
 * editor for create / update / delete.
 *
 * Guardrails can only be attached to metrics with `is_guardrail=true`
 * — the form dropdown filters to those metrics and shows an empty-state
 * hint when none are present.
 */
export default function GuardrailsTab({ experiment }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [editorOpen, setEditorOpen] = useState(false)
  const [editing, setEditing] = useState(null)  // null = create, else GuardrailConfig
  const [pendingDelete, setPendingDelete] = useState(null)

  const guardrailMetrics = (experiment?.metrics || []).filter((m) => m.is_guardrail)

  const { data, isLoading } = useQuery({
    queryKey: ['guardrails', experiment.id],
    queryFn: () => getGuardrails(experiment.id, { limit: 100 }),
    enabled: Boolean(experiment?.id),
  })

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['guardrails', experiment.id] })

  const deleteMutation = useMutation({
    mutationFn: (gid) => deleteGuardrail(experiment.id, gid),
    onSuccess: () => {
      invalidate()
      setPendingDelete(null)
      toast({ description: t('guardrails.deleted') })
    },
    onError: (err) => toast({
      variant: 'destructive',
      description: err.response?.data?.detail || t('errors.serverError'),
    }),
  })

  const items = data?.items || []
  const metricName = (id) => {
    const m = guardrailMetrics.find((x) => x.id === id)
    return m ? m.name : id
  }

  return (
    <ErrorBoundary>
      {guardrailMetrics.length === 0 ? (
        <Alert>
          <AlertDescription>{t('guardrails.noGuardrailMetrics')}</AlertDescription>
        </Alert>
      ) : (
        <>
          <div className="mb-4 flex justify-end">
            <Button
              size="sm"
              onClick={() => {
                setEditing(null)
                setEditorOpen(true)
              }}
            >
              <Plus className="mr-1 h-4 w-4" />
              {t('guardrails.new')}
            </Button>
          </div>
          {isLoading ? (
            <LoadingState />
          ) : items.length === 0 ? (
            <EmptyState
              title={t('guardrails.empty')}
              description={t('guardrails.emptyDescription')}
            />
          ) : (
            <Card>
              <CardContent className="p-0">
                <ul className="divide-y">
                  {items.map((g) => (
                    <li
                      key={g.id}
                      className="flex items-center justify-between gap-3 px-4 py-3"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="font-medium">{metricName(g.metric_id)}</div>
                        <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                          <Badge variant={g.severity === 'critical' ? 'destructive' : 'secondary'}>
                            {t(`guardrails.${g.severity}`)}
                          </Badge>
                          <span>
                            {g.direction === 'below' ? '↓' : '↑'}{' '}
                            {t(`guardrails.${g.direction}`)} {g.threshold_pct}%
                          </span>
                          {!g.is_enabled && (
                            <Badge variant="outline">{t('guardrails.isEnabled')} ✗</Badge>
                          )}
                        </div>
                      </div>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setEditing(g)
                            setEditorOpen(true)
                          }}
                          aria-label={t('common.edit')}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setPendingDelete(g)}
                          aria-label={t('common.delete')}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </>
      )}

      <GuardrailEditor
        open={editorOpen}
        onOpenChange={(open) => {
          setEditorOpen(open)
          if (!open) setEditing(null)
        }}
        experiment={experiment}
        editing={editing}
        onSaved={() => {
          invalidate()
          setEditorOpen(false)
          setEditing(null)
        }}
      />

      <Dialog
        open={!!pendingDelete}
        onOpenChange={(open) => !open && setPendingDelete(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('guardrails.deleted')}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {t('guardrails.deleteConfirm')}
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
    </ErrorBoundary>
  )
}

/**
 * Editor dialog for create + update. When `editing` is null we create
 * a new row; otherwise PATCH the existing one.
 *
 * The form is intentionally compact — guardrail config is a small
 * decision surface (metric + direction + threshold + severity +
 * enabled).
 */
function GuardrailEditor({ open, onOpenChange, experiment, editing, onSaved }) {
  const { t } = useTranslation()
  const [form, setForm] = useState(() => initialForm(experiment, editing))

  // When `editing` changes (e.g. clicking "edit" on a different row),
  // reset the form to that row's state.
  const [editingId, setEditingId] = useState(editing?.id ?? null)
  if (editingId !== (editing?.id ?? null)) {
    setForm(initialForm(experiment, editing))
    setEditingId(editing?.id ?? null)
  }

  const createMutation = useMutation({
    mutationFn: () => createGuardrail(experiment.id, {
      metric_id:     form.metric_id,
      direction:     form.direction,
      threshold_pct: Number(form.threshold_pct),
      severity:      form.severity,
      is_enabled:    form.is_enabled,
    }),
    onSuccess: () => {
      toast({ description: t('guardrails.created') })
      onSaved()
    },
    onError: (err) => toast({
      variant: 'destructive',
      description: err.response?.data?.detail || t('errors.serverError'),
    }),
  })

  const updateMutation = useMutation({
    mutationFn: () => updateGuardrail(experiment.id, editing.id, {
      threshold_pct: Number(form.threshold_pct),
      severity:      form.severity,
      is_enabled:    form.is_enabled,
    }),
    onSuccess: () => {
      toast({ description: t('guardrails.updated') })
      onSaved()
    },
    onError: (err) => toast({
      variant: 'destructive',
      description: err.response?.data?.detail || t('errors.serverError'),
    }),
  })

  const guardrailMetrics = (experiment?.metrics || []).filter((m) => m.is_guardrail)
  const saveDisabled =
    createMutation.isPending
    || updateMutation.isPending
    || !form.metric_id
    || !form.threshold_pct
    || Number(form.threshold_pct) <= 0

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {editing ? t('common.edit') : t('guardrails.new')}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="g-metric">{t('guardrails.metricLabel')}</Label>
            <select
              id="g-metric"
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={form.metric_id}
              onChange={(e) => setForm({ ...form, metric_id: e.target.value })}
              disabled={Boolean(editing)}
            >
              <option value="">{t('guardrails.metricPlaceholder')}</option>
              {guardrailMetrics.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="g-dir">{t('guardrails.directionLabel')}</Label>
              <Select
                value={form.direction}
                onValueChange={(v) => setForm({ ...form, direction: v })}
                disabled={Boolean(editing)}
              >
                <SelectTrigger id="g-dir">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="below">{t('guardrails.directionBelow')}</SelectItem>
                  <SelectItem value="above">{t('guardrails.directionAbove')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="g-thr">{t('guardrails.thresholdLabel')}</Label>
              <Input
                id="g-thr"
                type="number"
                step="0.1"
                min="0"
                max="100"
                value={form.threshold_pct}
                onChange={(e) => setForm({ ...form, threshold_pct: e.target.value })}
              />
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            {t('guardrails.thresholdHelp')}
          </p>
          <div className="space-y-1">
            <Label htmlFor="g-sev">{t('guardrails.severityLabel')}</Label>
            <Select
              value={form.severity}
              onValueChange={(v) => setForm({ ...form, severity: v })}
            >
              <SelectTrigger id="g-sev">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="warning">{t('guardrails.severityWarning')}</SelectItem>
                <SelectItem value="critical">{t('guardrails.severityCritical')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_enabled}
              onChange={(e) => setForm({ ...form, is_enabled: e.target.checked })}
            />
            {t('guardrails.isEnabled')}
          </label>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            {t('common.cancel')}
          </Button>
          <Button
            disabled={saveDisabled}
            onClick={() => {
              if (editing) updateMutation.mutate()
              else createMutation.mutate()
            }}
          >
            {t('common.save')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function initialForm(experiment, editing) {
  const firstGuardrail = (experiment?.metrics || []).find((m) => m.is_guardrail)
  if (editing) {
    return {
      metric_id:     editing.metric_id,
      direction:     editing.direction,
      threshold_pct: String(editing.threshold_pct),
      severity:      editing.severity,
      is_enabled:    editing.is_enabled,
    }
  }
  return {
    metric_id:     firstGuardrail?.id || '',
    direction:     'below',
    threshold_pct: '5',
    severity:      'warning',
    is_enabled:    true,
  }
}
