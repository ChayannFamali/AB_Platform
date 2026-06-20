import { useParams, useSearchParams, Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import {
  getExperiment,
  updateStatus,
} from '../api/client'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs'
import DecisionLogTab from '../components/experiment/DecisionLogTab'
import ExportButton from '../components/experiment/ExportButton'
import ExperimentResultsTab from '../components/experiment/ExperimentResultsTab'
import ExperimentSettingsTab from '../components/experiment/ExperimentSettingsTab'
import ExperimentStatusCard from '../components/experiment/ExperimentStatusCard'
import LoadingState from '../components/LoadingState'
import { PageHeader } from '../components/PageContainer'
import { toast } from '../hooks/use-toast'
import { useSSE } from '../hooks/useSSE'

const STATUS_VARIANT = {
  draft: 'secondary',
  running: 'success',
  paused: 'warning',
  completed: 'info',
}

const TABS = ['overview', 'results', 'decisions', 'settings']
const DEFAULT_TAB = 'overview'

export default function ExperimentDetailPage() {
  const { id } = useParams()
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()

  const currentTab = TABS.includes(searchParams.get('tab'))
    ? searchParams.get('tab')
    : DEFAULT_TAB

  const setTab = (next) => {
    if (next === DEFAULT_TAB) {
      searchParams.delete('tab')
    } else {
      searchParams.set('tab', next)
    }
    setSearchParams(searchParams, { replace: true })
  }

  const experimentQuery = useQuery({
    queryKey: ['experiment', id],
    queryFn: () => getExperiment(id).then((r) => r.data),
  })

  const statusMutation = useMutation({
    mutationFn: (status) => updateStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['experiment', id] })
      toast({
        description: t('experiments.list.statusUpdated', {
          defaultValue: 'Status updated',
        }),
      })
    },
    onError: (err) =>
      toast({
        variant: 'destructive',
        description: err.response?.data?.detail || t('errors.serverError'),
      }),
  })

  // SSE subscription (M-008). Auto-refresh TanStack Query on result_updated
  // and show toast notifications for alerts so the user sees them even
  // when they're on the Overview / Settings tabs.
  useSSE(id, {
    enabled: Boolean(id),
    onEvent: (eventType, data) => {
      if (eventType === 'result_updated') {
        queryClient.invalidateQueries({ queryKey: ['experiment', id] })
        queryClient.invalidateQueries({ queryKey: ['experiment-results', id] })
        queryClient.invalidateQueries({ queryKey: ['experiment-daily', id] })
        return
      }
      if (eventType === 'srm_alert') {
        toast({
          variant: 'destructive',
          title: t('sse.toast.srm.title'),
          description: t('sse.toast.srm.description', {
            p_value:
              data.p_value != null
                ? data.p_value.toExponential(2)
                : '—',
          }),
        })
      } else if (eventType === 'winner_detected') {
        toast({
          variant: 'success',
          title: t('sse.toast.winner.title'),
          description: t('sse.toast.winner.description', {
            lift: data.lift != null ? data.lift.toFixed(2) : '—',
          }),
        })
      } else if (eventType === 'guardrail_violated') {
        toast({
          variant: 'destructive',
          title: t('sse.toast.guardrail.title'),
          description: t('sse.toast.guardrail.description'),
        })
      } else if (eventType === 'sequential_boundary_crossed') {
        toast({
          variant: 'success',
          title: t('sse.toast.boundary.title'),
          description: t('sse.toast.boundary.description', {
            sequential_fpr:
              data.sequential_fpr != null
                ? data.sequential_fpr.toFixed(4)
                : '—',
          }),
        })
      }
    },
  })

  if (experimentQuery.isLoading) {
    return <LoadingState variant="spinner" label={t('experiments.results.loading')} />
  }
  if (experimentQuery.isError || !experimentQuery.data) {
    return (
      <div className="text-sm text-muted-foreground">
        {t('experiments.results.notFound')}
      </div>
    )
  }

  const exp = experimentQuery.data

  return (
    <>
      <PageHeader
        title={exp.name}
        description={exp.description}
        actions={
          <div className="flex items-center gap-2">
            <Badge variant={STATUS_VARIANT[exp.status] || 'secondary'}>
              {t(`experiments.list.${exp.status}`)}
            </Badge>
            {exp.status === 'draft' && (
              <Button
                onClick={() => statusMutation.mutate('running')}
                disabled={statusMutation.isLoading}
              >
                {t('experiments.list.start')}
              </Button>
            )}
            {exp.status === 'running' && (
              <Button
                variant="outline"
                onClick={() => statusMutation.mutate('paused')}
                disabled={statusMutation.isLoading}
              >
                {t('experiments.list.pause')}
              </Button>
            )}
            {exp.status === 'paused' && (
              <Button
                onClick={() => statusMutation.mutate('running')}
                disabled={statusMutation.isLoading}
              >
                {t('experiments.list.resume')}
              </Button>
            )}
            <ExportButton experimentId={id} />
          </div>
        }
      />

      <Link
        to="/"
        className="mb-4 inline-block text-sm text-muted-foreground hover:text-foreground"
      >
        ← {t('experiments.title')}
      </Link>

      <Tabs value={currentTab} onValueChange={setTab}>
        <TabsList className="mb-4">
          <TabsTrigger value="overview">
            {t('experiments.tabs.overview')}
          </TabsTrigger>
          <TabsTrigger value="results">
            {t('experiments.tabs.results')}
          </TabsTrigger>
          <TabsTrigger value="decisions">
            {t('experiments.tabs.decisions')}
          </TabsTrigger>
          <TabsTrigger value="settings">
            {t('experiments.tabs.settings')}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <ExperimentStatusCard experiment={exp} />
        </TabsContent>

        <TabsContent value="results">
          <ExperimentResultsTab
            experimentId={id}
            experimentStatus={exp.status}
            isSequential={exp.is_sequential}
          />
        </TabsContent>

        <TabsContent value="decisions">
          <DecisionLogTab />
        </TabsContent>

        <TabsContent value="settings">
          <ExperimentSettingsTab experiment={exp} />
        </TabsContent>
      </Tabs>
    </>
  )
}
