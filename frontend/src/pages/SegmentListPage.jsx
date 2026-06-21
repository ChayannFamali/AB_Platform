import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Plus, Trash2 } from 'lucide-react'

import {
  createSegment,
  deleteSegment,
  getSegments,
} from '../api/client'
import PageContainer from '../components/PageContainer'
import EmptyState from '../components/EmptyState'
import LoadingState from '../components/LoadingState'
import ErrorBoundary from '../components/ErrorBoundary'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import { Card, CardContent } from '../components/ui/card'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from '../components/ui/dialog'
import { toast } from '../hooks/use-toast'

const KEY_RE = /^[a-z0-9][a-z0-9_-]*$/

export default function SegmentListPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [showDialog, setShowDialog] = useState(false)
  const [form, setForm] = useState({ key: '', name: '', description: '' })
  const [pendingDelete, setPendingDelete] = useState(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['segments'],
    queryFn: () => getSegments({ limit: 100 }),
  })

  const createMutation = useMutation({
    mutationFn: () => createSegment({ ...form, rules: [] }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['segments'] })
      setShowDialog(false)
      setForm({ key: '', name: '', description: '' })
      toast({ description: t('segments.created') })
    },
    onError: (err) => toast({
      variant: 'destructive',
      description: err.response?.data?.detail || t('errors.serverError'),
    }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => deleteSegment(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['segments'] })
      setPendingDelete(null)
      toast({ description: t('segments.deleted') })
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
    <PageContainer
      title={t('segments.title')}
      subtitle={t('segments.subtitle')}
      actions={
        <Button onClick={() => setShowDialog(true)}>
          <Plus className="mr-1 h-4 w-4" /> {t('segments.new')}
        </Button>
      }
    >
      <ErrorBoundary>
        {isLoading ? (
          <LoadingState />
        ) : error ? (
          <EmptyState title={t('errors.serverError')} />
        ) : items.length === 0 ? (
          <EmptyState
            title={t('segments.empty')}
            description={t('segments.emptyDescription')}
          />
        ) : (
          <Card>
            <CardContent className="p-0">
              <ul className="divide-y">
                {items.map((s) => (
                  <li
                    key={s.id}
                    className="flex items-center justify-between gap-3 px-4 py-3"
                  >
                    <div className="min-w-0 flex-1">
                      <Link
                        to={`/segments/${encodeURIComponent(s.key)}`}
                        className="font-medium hover:underline"
                      >
                        {s.name}
                      </Link>
                      <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                        <code className="rounded bg-muted px-1.5 py-0.5">{s.key}</code>
                        <span>·</span>
                        <span>{t('segments.rulesCount', { count: s.rules_count })}</span>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setPendingDelete(s)}
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

      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('segments.new')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <Label htmlFor="seg-key">{t('segments.keyLabel')}</Label>
              <Input
                id="seg-key"
                value={form.key}
                onChange={(e) => setForm({ ...form, key: e.target.value })}
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
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setShowDialog(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              onClick={() => createMutation.mutate()}
              disabled={
                createMutation.isPending
                || !form.key
                || !form.name
                || !!keyError
              }
            >
              {t('common.create')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!pendingDelete} onOpenChange={(open) => !open && setPendingDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('segments.delete')}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {t('segments.deleteConfirm', { name: pendingDelete?.name })}
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
