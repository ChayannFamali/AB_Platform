import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Plus, Send, Trash2, Webhook as WebhookIcon } from 'lucide-react'

import {
  createWebhook,
  deleteWebhook,
  getWebhooks,
  testWebhook,
  updateWebhook,
} from '../api/client'
import WebhookForm from '../components/webhooks/WebhookForm'
import WebhookDeliveryLog from '../components/webhooks/WebhookDeliveryLog'
import EmptyState from '../components/EmptyState'
import ErrorBoundary from '../components/ErrorBoundary'
import LoadingState from '../components/LoadingState'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent } from '../components/ui/card'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from '../components/ui/dialog'
import { PageHeader } from '../components/PageContainer'
import { toast } from '../hooks/use-toast'

/**
 * /settings/webhooks — list, create, edit, delete, test webhooks.
 * The list shows a one-row-per-webhook summary; clicking a row expands
 * the inline delivery log. The "Test" button fires a synchronous
 * request and toasts the result code + duration.
 */
export default function WebhookSettingsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [editorOpen, setEditorOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [expanded, setExpanded] = useState(null)
  const [pendingDelete, setPendingDelete] = useState(null)
  const [lastSecret, setLastSecret] = useState(null)

  const { data, isLoading } = useQuery({
    queryKey: ['webhooks'],
    queryFn: () => getWebhooks({ limit: 100 }),
  })
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['webhooks'] })

  const createMutation = useMutation({
    mutationFn: (body) => createWebhook(body),
    onSuccess: (resp) => {
      invalidate()
      setEditorOpen(false)
      setEditing(null)
      if (resp?.secret) {
        setLastSecret({ name: resp.name, secret: resp.secret })
        toast({ description: t('webhooks.created') })
      }
    },
    onError: (err) =>
      toast({
        variant: 'destructive',
        description: err.response?.data?.detail || t('errors.serverError'),
      }),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, body }) => updateWebhook(id, body),
    onSuccess: () => {
      invalidate()
      setEditorOpen(false)
      setEditing(null)
      toast({ description: t('webhooks.updated') })
    },
    onError: (err) =>
      toast({
        variant: 'destructive',
        description: err.response?.data?.detail || t('errors.serverError'),
      }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => deleteWebhook(id),
    onSuccess: () => {
      invalidate()
      setPendingDelete(null)
      toast({ description: t('webhooks.deleted') })
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
      <PageHeader
        title={t('webhooks.title')}
        description={t('webhooks.subtitle')}
        actions={
          <Button
            size="sm"
            onClick={() => {
              setEditing(null)
              setEditorOpen(true)
            }}
          >
            <Plus className="mr-1 h-4 w-4" />
            {t('webhooks.new')}
          </Button>
        }
      />

      {isLoading ? (
        <LoadingState />
      ) : items.length === 0 ? (
        <EmptyState
          icon={WebhookIcon}
          title={t('webhooks.empty')}
          description={t('webhooks.emptyHint')}
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <ul className="divide-y">
              {items.map((w) => (
                <li key={w.id} className="px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <button
                      type="button"
                      className="min-w-0 flex-1 text-left"
                      onClick={() => setExpanded(expanded === w.id ? null : w.id)}
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{w.name}</span>
                        <Badge variant="outline">{w.format}</Badge>
                        {!w.is_active && (
                          <Badge variant="secondary">
                            {t('webhooks.paused')}
                          </Badge>
                        )}
                        <span className="text-xs text-muted-foreground">
                          {w.events.length} {t('webhooks.eventsCount')}
                        </span>
                      </div>
                      <div className="mt-0.5 truncate text-xs text-muted-foreground">
                        {w.url}
                      </div>
                    </button>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleTest(w)}
                        aria-label={t('webhooks.test')}
                      >
                        <Send className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setEditing(w)
                          setEditorOpen(true)
                        }}
                        aria-label={t('common.edit')}
                      >
                        <WebhookIcon className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setPendingDelete(w)}
                        aria-label={t('common.delete')}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                  {expanded === w.id && (
                    <div className="mt-3 border-t pt-3">
                      <WebhookDeliveryLog webhookId={w.id} />
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <WebhookForm
        open={editorOpen}
        onOpenChange={(o) => {
          setEditorOpen(o)
          if (!o) setEditing(null)
        }}
        editing={editing}
        submitting={createMutation.isPending || updateMutation.isPending}
        onSubmit={async (body) => {
          if (editing) {
            await updateMutation.mutateAsync({ id: editing.id, body })
            return null
          }
          return createMutation.mutateAsync(body)
        }}
        onCreated={() => {
          // The form already closes itself on submit, but the secret
          // dialog is shown via `lastSecret` state below.
        }}
      />

      {/* One-time secret reveal after create */}
      <Dialog
        open={Boolean(lastSecret)}
        onOpenChange={(o) => !o && setLastSecret(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('webhooks.secretRevealTitle')}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {t('webhooks.secretRevealHint')}
          </p>
          {lastSecret && (
            <code className="block break-all rounded bg-muted px-3 py-2 font-mono text-sm">
              {lastSecret.secret}
            </code>
          )}
          <DialogFooter>
            <Button onClick={() => setLastSecret(null)}>
              {t('webhooks.secretSaved')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog
        open={Boolean(pendingDelete)}
        onOpenChange={(o) => !o && setPendingDelete(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('webhooks.deleteConfirmTitle')}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {t('webhooks.deleteConfirm', { name: pendingDelete?.name || '' })}
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

  async function handleTest(webhook) {
    try {
      const resp = await testWebhook(webhook.id)
      toast({
        variant: resp.success ? 'success' : 'destructive',
        description: t('webhooks.testResult', {
          status: resp.status_code,
          duration: resp.duration_ms,
        }),
      })
    } catch (err) {
      toast({
        variant: 'destructive',
        description: err.response?.data?.detail || t('errors.serverError'),
      })
    }
  }
}