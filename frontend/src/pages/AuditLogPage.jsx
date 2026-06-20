import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { ScrollText } from 'lucide-react'

import { getAuditLog } from '../api/client'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
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
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import { Alert, AlertDescription } from '../components/ui/alert'
import EmptyState from '../components/EmptyState'
import LoadingState from '../components/LoadingState'
import { PageHeader } from '../components/PageContainer'

const LIMIT = 30
const RESOURCE_TYPES = ['', 'role', 'user', 'user_role']
const ACTIONS        = ['', 'create', 'update', 'assign', 'revoke', 'toggle_active']

const ACTION_VARIANT = {
  create:        'success',
  update:        'info',
  delete:        'destructive',
  assign:        'success',
  revoke:        'warning',
  toggle_active: 'secondary',
}

export default function AuditLogPage() {
  const { t, i18n } = useTranslation()
  const [offset, setOffset] = useState(0)
  const [filters, setFilters] = useState({
    resource_type: '',
    action: '',
  })

  const params = { limit: LIMIT, offset }
  if (filters.resource_type) params.resource_type = filters.resource_type
  if (filters.action) params.action = filters.action

  const auditQuery = useQuery({
    queryKey: ['audit', params],
    queryFn: () => getAuditLog(params).then((r) => r.data),
    keepPreviousData: true,
  })

  const items = auditQuery.data?.items ?? []
  const total = auditQuery.data?.total ?? 0
  const from = total === 0 ? 0 : offset + 1
  const to = Math.min(offset + LIMIT, total)

  const handlePrev = () => setOffset(Math.max(0, offset - LIMIT))
  const handleNext = () => {
    if (offset + LIMIT < total) setOffset(offset + LIMIT)
  }

  const handleFilterChange = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }))
    setOffset(0)
  }

  const localeForDate = i18n.language === 'en' ? 'en-US' : 'ru-RU'

  return (
    <>
      <PageHeader
        title={t('audit.title')}
        description={t('audit.subtitle')}
      />

      <Card className="mb-4">
        <CardContent className="grid gap-4 p-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="audit-resource-type">
              {t('audit.resourceType')}
            </Label>
            <select
              id="audit-resource-type"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={filters.resource_type}
              onChange={(e) => handleFilterChange('resource_type', e.target.value)}
            >
              {RESOURCE_TYPES.map((rt) => (
                <option key={rt || 'all'} value={rt}>
                  {rt === ''
                    ? t('common.all')
                    : t(`audit.resourceType_${rt}`, { defaultValue: rt })}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="audit-action">{t('audit.action')}</Label>
            <select
              id="audit-action"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={filters.action}
              onChange={(e) => handleFilterChange('action', e.target.value)}
            >
              {ACTIONS.map((a) => (
                <option key={a || 'all'} value={a}>
                  {a === ''
                    ? t('common.all')
                    : t(`audit.action_${a}`, { defaultValue: a })}
                </option>
              ))}
            </select>
          </div>
        </CardContent>
      </Card>

      {auditQuery.isError && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>
            {auditQuery.error?.response?.data?.detail || t('errors.serverError')}
          </AlertDescription>
        </Alert>
      )}

      {auditQuery.isLoading ? (
        <LoadingState variant="skeleton" count={5} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={ScrollText}
          title={t('audit.empty')}
          description={t('audit.emptyDescription')}
        />
      ) : (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">
              {t('audit.title')} ({total})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('audit.when')}</TableHead>
                  <TableHead>{t('audit.actor')}</TableHead>
                  <TableHead>{t('audit.action')}</TableHead>
                  <TableHead>{t('audit.resourceType')}</TableHead>
                  <TableHead className="text-right">
                    {t('audit.details')}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell className="text-muted-foreground">
                      {new Date(entry.created_at).toLocaleString(localeForDate)}
                    </TableCell>
                    <TableCell>
                      {entry.user_username || (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge variant={ACTION_VARIANT[entry.action] || 'secondary'}>
                        {t(`audit.action_${entry.action}`, { defaultValue: entry.action })}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <code className="text-xs text-muted-foreground">
                        {entry.resource_type}
                        {entry.resource_id && (
                          <>
                            {' / '}
                            {String(entry.resource_id).slice(0, 8)}
                          </>
                        )}
                      </code>
                    </TableCell>
                    <TableCell className="max-w-md text-right">
                      {entry.details ? (
                        <code className="block truncate text-xs text-muted-foreground">
                          {JSON.stringify(entry.details)}
                        </code>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            {total > LIMIT && (
              <div className="mt-4 flex items-center justify-between border-t pt-4">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handlePrev}
                  disabled={offset === 0}
                >
                  {t('common.back')}
                </Button>
                <span className="text-sm text-muted-foreground">
                  {t('experiments.list.range', { from, to, total })}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleNext}
                  disabled={offset + LIMIT >= total}
                >
                  {t('common.next')}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </>
  )
}