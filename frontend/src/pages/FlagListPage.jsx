import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Flag, Plus, Trash2 } from 'lucide-react'

import {
  createFlag,
  deleteFlag,
  getFlags,
} from '../api/client'
import { Button } from '../components/ui/button'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '../components/ui/card'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog'
import { Alert, AlertDescription } from '../components/ui/alert'
import FlagToggle from '../components/flags/FlagToggle'
import FlagStatusBadge from '../components/flags/FlagStatusBadge'
import EmptyState from '../components/EmptyState'
import LoadingState from '../components/LoadingState'
import { PageHeader } from '../components/PageContainer'
import { toast } from '../hooks/use-toast'

const KEY_RE = /^[a-z0-9][a-z0-9_-]*$/

export default function FlagListPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [newKey, setNewKey] = useState('')
  const [newName, setNewName] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [newRollout, setNewRollout] = useState(0)
  const [createError, setCreateError] = useState(null)

  const flagsQuery = useQuery({
    queryKey: ['flags'],
    queryFn: () => getFlags({ limit: 100 }),
  })

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['flags'] })

  const createMutation = useMutation({
    mutationFn: () => createFlag({
      key: newKey,
      name: newName,
      description: newDescription || null,
      enabled: true,
      rollout_percentage: newRollout,
      rules: [],
    }),
    onSuccess: () => {
      invalidate()
      setCreateOpen(false)
      setNewKey('')
      setNewName('')
      setNewDescription('')
      setNewRollout(0)
      setCreateError(null)
      toast({ description: t('flags.created') })
    },
    onError: (err) => {
      const detail = err.response?.data?.detail
      setCreateError(
        Array.isArray(detail)
          ? detail.map((d) => d.msg).join(', ')
          : detail || t('errors.serverError'),
      )
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => deleteFlag(id),
    onSuccess: () => {
      invalidate()
      toast({ description: t('flags.deleted') })
    },
    onError: (err) => toast({
      variant: 'destructive',
      description: err.response?.data?.detail || t('errors.serverError'),
    }),
  })

  const flags = flagsQuery.data?.items ?? []
  const summary = flagsQuery.data?.summary

  const handleSubmit = (e) => {
    e.preventDefault()
    setCreateError(null)
    if (!KEY_RE.test(newKey)) {
      setCreateError(t('flags.errors.keyFormat'))
      return
    }
    createMutation.mutate()
  }

  return (
    <>
      <PageHeader
        title={t('flags.title')}
        description={t('flags.subtitle')}
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="mr-1 h-4 w-4" />
            {t('flags.new')}
          </Button>
        }
      />

      {summary && (
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <SummaryStat label={t('flags.total')} value={summary.total} />
          <SummaryStat
            label={t('flags.enabled')}
            value={summary.enabled_total}
            tone="success"
          />
          <SummaryStat
            label={t('flags.serving')}
            value={summary.enabled_with_rollout}
          />
          <SummaryStat
            label={t('flags.disabled')}
            value={summary.disabled_total}
            tone="destructive"
          />
        </div>
      )}

      {flagsQuery.isError && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>
            {flagsQuery.error?.response?.data?.detail || t('errors.serverError')}
          </AlertDescription>
        </Alert>
      )}

      {flagsQuery.isLoading ? (
        <LoadingState variant="skeleton" count={4} />
      ) : flags.length === 0 ? (
        <EmptyState
          icon={Flag}
          title={t('flags.empty')}
          description={t('flags.emptyDescription')}
        />
      ) : (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">
              {t('flags.title')} ({flags.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="divide-y">
            {flags.map((flag) => (
              <div
                key={flag.id}
                className="flex items-center gap-3 py-3"
              >
                <FlagStatusBadge flag={flag} />
                <div className="flex-1 min-w-0">
                  <Link
                    to={`/flags/${encodeURIComponent(flag.key)}`}
                    className="block truncate font-medium hover:underline"
                  >
                    {flag.name}
                  </Link>
                  <code className="text-xs text-muted-foreground">
                    {flag.key}
                  </code>
                </div>
                <div className="hidden text-sm text-muted-foreground sm:block">
                  {t('flags.rolloutShort', { pct: flag.rollout_percentage })}
                </div>
                <FlagToggle flag={flag} />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    if (window.confirm(t('flags.deleteConfirm', { name: flag.name }))) {
                      deleteMutation.mutate(flag.id)
                    }
                  }}
                  aria-label={t('flags.delete')}
                  disabled={deleteMutation.isPending}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('flags.new')}</DialogTitle>
            <DialogDescription>{t('flags.newHelp')}</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="space-y-1">
              <Label htmlFor="flag-key">{t('flags.keyLabel')}</Label>
              <Input
                id="flag-key"
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
                placeholder="new_checkout"
                required
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="flag-name">{t('flags.nameLabel')}</Label>
              <Input
                id="flag-name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder={t('flags.namePlaceholder')}
                required
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="flag-description">{t('flags.description')}</Label>
              <Input
                id="flag-description"
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="flag-rollout">{t('flags.rolloutInitial')}</Label>
              <Input
                id="flag-rollout"
                type="number"
                min={0}
                max={100}
                value={newRollout}
                onChange={(e) => setNewRollout(Number(e.target.value))}
              />
            </div>
            {createError && (
              <Alert variant="destructive">
                <AlertDescription>{createError}</AlertDescription>
              </Alert>
            )}
            <DialogFooter>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setCreateOpen(false)}
              >
                {t('common.cancel')}
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {t('common.create')}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}

function SummaryStat({ label, value, tone }) {
  const toneClass =
    tone === 'success'
      ? 'text-emerald-600 dark:text-emerald-400'
      : tone === 'destructive'
      ? 'text-destructive'
      : 'text-foreground'
  return (
    <div className="rounded border bg-card p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={`mt-1 text-xl font-semibold ${toneClass}`}>
        {value}
      </div>
    </div>
  )
}