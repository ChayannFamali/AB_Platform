import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Beaker, Plus } from 'lucide-react'

import {
  deleteExperiment,
  getExperiments,
  updateStatus,
} from '../api/client'
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
import { Alert, AlertDescription } from '../components/ui/alert'
import EmptyState from '../components/EmptyState'
import LoadingState from '../components/LoadingState'
import { PageHeader } from '../components/PageContainer'
import { toast } from '../hooks/use-toast'

const STATUS_VARIANT = {
  draft: 'secondary',
  running: 'success',
  paused: 'warning',
  completed: 'info',
}

const LIMIT = 20

export default function ExperimentList() {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const [offset, setOffset] = useState(0)
  const [statusFilter, setStatusFilter] = useState('')

  const filters = { limit: LIMIT, offset }
  if (statusFilter) filters.status = statusFilter

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['experiments', filters],
    queryFn: () => getExperiments(filters).then((r) => r.data),
    keepPreviousData: true,
  })

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['experiments'] })

  const statusMutation = useMutation({
    mutationFn: ({ id, status }) => updateStatus(id, status),
    onSuccess: () => {
      invalidate()
      toast({ description: t('experiments.list.statusUpdated', { defaultValue: 'Status updated' }) })
    },
    onError: (err) =>
      toast({
        variant: 'destructive',
        description: err.response?.data?.detail || t('errors.serverError'),
      }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => deleteExperiment(id),
    onSuccess: () => {
      invalidate()
      toast({ description: t('experiments.list.deleted', { defaultValue: 'Deleted' }) })
    },
    onError: (err) =>
      toast({
        variant: 'destructive',
        description: err.response?.data?.detail || t('errors.serverError'),
      }),
  })

  const items = data?.items ?? []
  const total = data?.total ?? 0

  const handleStatusFilter = (s) => {
    setStatusFilter(s)
    setOffset(0)
  }

  const handlePrev = () => setOffset(Math.max(0, offset - LIMIT))
  const handleNext = () => setOffset(offset + LIMIT)

  const handleDelete = (id) => {
    if (!window.confirm(t('experiments.list.deleteConfirm'))) return
    deleteMutation.mutate(id)
  }

  const from = total === 0 ? 0 : offset + 1
  const to = Math.min(offset + LIMIT, total)
  const totalPages = Math.ceil(total / LIMIT) || 1
  const currentPage = Math.floor(offset / LIMIT) + 1

  return (
    <>
      <PageHeader
        title={t('experiments.title')}
        description={
          !isLoading
            ? t('experiments.list.total', { count: total })
            : undefined
        }
        actions={
          <Button asChild>
            <Link to="/experiments/new">
              <Plus className="mr-1 h-4 w-4" />
              {t('experiments.new')}
            </Link>
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap gap-2">
        {['', 'draft', 'running', 'paused', 'completed'].map((s) => (
          <Button
            key={s || 'all'}
            variant={statusFilter === s ? 'default' : 'outline'}
            size="sm"
            onClick={() => handleStatusFilter(s)}
          >
            {s === ''
              ? t('common.all')
              : t(`experiments.list.${s}`)}
          </Button>
        ))}
      </div>

      {isError && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>
            {error?.response?.data?.detail || t('errors.serverError')}
          </AlertDescription>
        </Alert>
      )}

      {isLoading ? (
        <LoadingState variant="skeleton" count={5} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Beaker}
          title={t('common.noData')}
          description={
            statusFilter
              ? t('experiments.list.emptyFiltered', {
                  status: t(`experiments.list.${statusFilter}`),
                })
              : t('experiments.list.empty')
          }
          action={
            <Button asChild>
              <Link to="/experiments/new">
                <Plus className="mr-1 h-4 w-4" />
                {t('experiments.new')}
              </Link>
            </Button>
          }
        />
      ) : (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">
              {t('experiments.title')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('experiments.create.name')}</TableHead>
                  <TableHead>{t('experiments.create.status')}</TableHead>
                  <TableHead>{t('experiments.list.traffic')}</TableHead>
                  <TableHead>{t('experiments.list.created')}</TableHead>
                  <TableHead className="text-right">
                    {t('common.actions')}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((exp) => (
                  <TableRow key={exp.id}>
                    <TableCell>
                      <Link
                        to={`/experiments/${exp.id}`}
                        className="font-medium text-primary hover:underline"
                      >
                        {exp.name}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Badge variant={STATUS_VARIANT[exp.status] || 'secondary'}>
                        {t(`experiments.list.${exp.status}`)}
                      </Badge>
                    </TableCell>
                    <TableCell>{exp.traffic_percentage}%</TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(exp.created_at).toLocaleDateString(
                        i18n.language === 'en' ? 'en-US' : 'ru-RU'
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button asChild variant="outline" size="sm">
                          <Link to={`/experiments/${exp.id}`}>
                            {t('experiments.list.open')}
                          </Link>
                        </Button>
                        {exp.status === 'draft' && (
                          <Button
                            variant="default"
                            size="sm"
                            onClick={() =>
                              statusMutation.mutate({
                                id: exp.id,
                                status: 'running',
                              })
                            }
                          >
                            {t('experiments.list.start')}
                          </Button>
                        )}
                        {exp.status === 'running' && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() =>
                              statusMutation.mutate({
                                id: exp.id,
                                status: 'paused',
                              })
                            }
                          >
                            {t('experiments.list.pause')}
                          </Button>
                        )}
                        {exp.status === 'paused' && (
                          <Button
                            variant="default"
                            size="sm"
                            onClick={() =>
                              statusMutation.mutate({
                                id: exp.id,
                                status: 'running',
                              })
                            }
                          >
                            {t('experiments.list.resume')}
                          </Button>
                        )}
                        {(exp.status === 'draft' ||
                          exp.status === 'completed') && (
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => handleDelete(exp.id)}
                          >
                            {t('experiments.list.delete')}
                          </Button>
                        )}
                      </div>
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
                  {' · '}
                  {t('experiments.list.page', {
                    current: currentPage,
                    total: totalPages,
                  })}
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