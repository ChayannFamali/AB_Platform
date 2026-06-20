import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Key, Plus, Copy, Trash2 } from 'lucide-react'

import {
  createApiKey,
  getApiKeys,
  revokeApiKey,
} from '../api/client'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '../components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table'
import { Alert, AlertDescription } from '../components/ui/alert'
import EmptyState from '../components/EmptyState'
import LoadingState from '../components/LoadingState'
import { PageHeader } from '../components/PageContainer'
import { toast } from '../hooks/use-toast'

export default function ApiKeysPage() {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const [newName, setNewName] = useState('')
  const [createdKey, setCreatedKey] = useState(null)

  const keysQuery = useQuery({
    queryKey: ['api-keys'],
    queryFn: () => getApiKeys().then((r) => r.data),
  })

  const createMutation = useMutation({
    mutationFn: (name) => createApiKey({ name }),
    onSuccess: (response) => {
      setCreatedKey(response.data.key)
      setNewName('')
      queryClient.invalidateQueries({ queryKey: ['api-keys'] })
      toast({ description: t('apiKeys.createSuccess') })
    },
    onError: (err) =>
      toast({
        variant: 'destructive',
        description: err.response?.data?.detail || t('errors.serverError'),
      }),
  })

  const revokeMutation = useMutation({
    mutationFn: (id) => revokeApiKey(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] })
      toast({ description: t('apiKeys.revoked', { defaultValue: 'Key revoked' }) })
    },
    onError: (err) =>
      toast({
        variant: 'destructive',
        description: err.response?.data?.detail || t('errors.serverError'),
      }),
  })

  const handleCreate = (e) => {
    e.preventDefault()
    if (!newName.trim()) return
    createMutation.mutate(newName.trim())
  }

  const handleRevoke = (id, name) => {
    if (!window.confirm(t('apiKeys.revokeConfirm', { name }))) return
    revokeMutation.mutate(id)
  }

  const handleCopy = (key) => {
    if (navigator?.clipboard) {
      navigator.clipboard.writeText(key).then(() =>
        toast({ description: t('apiKeys.copied') }),
      )
    }
  }

  return (
    <>
      <PageHeader
        title={t('apiKeys.title')}
        icon={Key}
      />

      {createdKey && (
        <Alert variant="success" className="mb-6">
          <AlertDescription>
            <div className="mb-2 font-semibold">
              {t('apiKeys.createSuccess')}
            </div>
            <div className="mb-2 text-sm">
              {t('apiKeys.warning')}
            </div>
            <div className="flex items-center gap-2">
              <code className="flex-1 break-all rounded bg-emerald-50 p-2 text-xs dark:bg-emerald-950">
                {createdKey}
              </code>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleCopy(createdKey)}
              >
                <Copy className="mr-1 h-4 w-4" />
                {t('apiKeys.copy')}
              </Button>
            </div>
            <Button
              size="sm"
              variant="ghost"
              className="mt-2"
              onClick={() => setCreatedKey(null)}
            >
              {t('common.cancel')}
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">{t('apiKeys.create')}</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={handleCreate}
            className="flex flex-col gap-3 sm:flex-row"
          >
            <div className="flex-1 space-y-1">
              <Label htmlFor="key-name">{t('apiKeys.name')}</Label>
              <Input
                id="key-name"
                placeholder="Production Backend"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
              />
            </div>
            <div className="flex items-end">
              <Button
                type="submit"
                disabled={createMutation.isLoading || !newName.trim()}
              >
                <Plus className="mr-1 h-4 w-4" />
                {createMutation.isLoading
                  ? t('common.loading')
                  : t('apiKeys.create')}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">{t('apiKeys.title')}</CardTitle>
        </CardHeader>
        <CardContent>
          {keysQuery.isLoading ? (
            <LoadingState variant="spinner" count={3} />
          ) : keysQuery.isError ? (
            <Alert variant="destructive">
              <AlertDescription>
                {keysQuery.error?.response?.data?.detail ||
                  t('errors.serverError')}
              </AlertDescription>
            </Alert>
          ) : keysQuery.data?.length === 0 ? (
            <EmptyState
              icon={Key}
              title={t('common.noData')}
              description={t('apiKeys.empty')}
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('apiKeys.name')}</TableHead>
                  <TableHead>{t('apiKeys.key')}</TableHead>
                  <TableHead>{t('apiKeys.created')}</TableHead>
                  <TableHead>{t('apiKeys.lastUsed')}</TableHead>
                  <TableHead className="text-right">
                    {t('common.actions')}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(keysQuery.data || []).map((k) => (
                  <TableRow key={k.id}>
                    <TableCell className="font-medium">{k.name}</TableCell>
                    <TableCell>
                      <code className="text-xs text-muted-foreground">
                        {k.key_preview}
                      </code>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(k.created_at).toLocaleDateString(
                        i18n.language === 'en' ? 'en-US' : 'ru-RU',
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {k.last_used_at
                        ? new Date(k.last_used_at).toLocaleString(
                            i18n.language === 'en' ? 'en-US' : 'ru-RU',
                          )
                        : '—'}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => handleRevoke(k.id, k.name)}
                      >
                        <Trash2 className="mr-1 h-4 w-4" />
                        {t('apiKeys.revoke')}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {t('apiKeys.sdkUsage', { defaultValue: 'SDK usage' })}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-100">
{`# Python SDK
from abplatform import ABPlatformClient
client = ABPlatformClient(
    api_url="http://your-server:8000",
    api_key="abp_your_key_here",
)

# JS SDK
const client = new ABPlatformClient({
  apiUrl: 'http://your-server:8000',
  apiKey: 'abp_your_key_here',
});`}
          </pre>
        </CardContent>
      </Card>
    </>
  )
}