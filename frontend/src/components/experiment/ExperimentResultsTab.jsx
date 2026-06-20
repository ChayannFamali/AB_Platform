import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import {
  analyzeExperiment,
  getDailyResults,
  getResults,
} from '../../api/client'
import { Alert, AlertDescription } from '../ui/alert'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import EmptyState from '../EmptyState'
import LoadingState from '../LoadingState'
import InsightPanel from '../stats/InsightPanel'
import SequentialPValueChart from '../stats/SequentialPValueChart'
import SignificanceBadge from '../stats/SignificanceBadge'
import SRMAlert from '../stats/SRMAlert'
import TestBadge from '../stats/TestBadge'
import { toast } from '../../hooks/use-toast'

const fmt = (v, type) => {
  if (v == null) return '—'
  if (type === 'conversion') return `${(v * 100).toFixed(2)}%`
  return v.toFixed(4)
}

const fmtMde = (mde, metricType) => {
  if (mde == null) return null
  if (metricType === 'conversion') return `${(mde * 100).toFixed(2)}%`
  return mde.toFixed(2)
}

const formatSnapshotDate = (dateStr) => {
  const parts = dateStr.split('-')
  return `${parts[2]}.${parts[1]}`
}

const LINE_COLORS = [
  '#4f46e5', '#059669', '#dc2626', '#d97706', '#7c3aed', '#0891b2',
]

function NormalityTag({ isNormal }) {
  if (isNormal == null) return null
  return isNormal === false ? (
    <span
      className="cursor-help text-xs text-amber-600"
      title="Shapiro-Wilk p < 0.05 — ненормальное распределение"
    >
      ⚠ Non-normal
    </span>
  ) : (
    <span
      className="cursor-help text-xs text-emerald-600"
      title="Shapiro-Wilk: нормальное распределение"
    >
      ✓ Normal
    </span>
  )
}

function TestBadgeWithNormality({ testUsed, isNormal }) {
  const showNormality =
    (testUsed === 'welch_t_test' || testUsed === 'mann_whitney') &&
    isNormal != null
  return (
    <div className="flex flex-col items-start gap-1">
      <TestBadge testUsed={testUsed} />
      {showNormality && <NormalityTag isNormal={isNormal} />}
    </div>
  )
}

function AchievedMdeBlock({ metric }) {
  const targets = (metric.variants || []).filter(
    (v) =>
      v.variant_name !== 'control' &&
      v.is_significant === false &&
      v.achieved_mde != null,
  )
  if (targets.length === 0) return null
  return (
    <Alert variant="info" className="mb-6">
      <AlertDescription>
        <div className="mb-2 font-semibold">📏 Чувствительность теста</div>
        <div className="mb-2 text-sm">
          Результат незначим. При текущей выборке платформа обнаружила бы следующий минимальный эффект:
        </div>
        {targets.map((v) => {
          const mde = fmtMde(v.achieved_mde, metric.metric_type)
          if (!mde) return null
          return (
            <div key={v.variant_id} className="mt-1 text-sm">
              <strong>{v.variant_name}</strong>
              <span className="text-muted-foreground">
                {' '}
                (N={v.sample_size.toLocaleString()})
              </span>
              {' → '}
              видим эффект ≥{' '}
              <strong className="text-blue-700">{mde}</strong>
              {metric.metric_type === 'conversion' ? ' по конверсии' : ''}.
              Если реальный эффект меньше — увеличьте выборку.
            </div>
          )
        })}
      </AlertDescription>
    </Alert>
  )
}

function DecompositionBlock({ variants }) {
  const withDecomp = (variants || []).filter(
    (v) => v.variant_name !== 'control' && v.numerator_relative_lift != null,
  )
  if (withDecomp.length === 0) return null
  const liftColor = (val) =>
    val == null
      ? 'text-gray-400'
      : val >= 0
        ? 'text-emerald-600'
        : 'text-red-600'
  const liftFmt = (val) =>
    val == null ? '—' : `${val >= 0 ? '+' : ''}${val.toFixed(1)}%`
  return (
    <div className="mb-6">
      <h3 className="mb-2 text-sm font-semibold text-muted-foreground">
        🔬 Декомпозиция эффекта
      </h3>
      <p className="mb-3 text-xs text-muted-foreground">
        Откуда взялся итоговый lift ratio метрики — из числителя, знаменателя или обоих.
      </p>
      {withDecomp.map((v) => (
        <div
          key={v.variant_id}
          className="mb-2 rounded-lg border bg-muted/40 p-4"
        >
          <div className="mb-3 text-sm font-semibold">{v.variant_name}</div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <div className="mb-1 text-xs text-muted-foreground">Ratio (итог)</div>
              <div className={`text-base font-bold ${liftColor(v.relative_lift)}`}>
                {liftFmt(v.relative_lift)}
              </div>
            </div>
            <div>
              <div className="mb-1 text-xs text-muted-foreground">└ Числитель</div>
              <div
                className={`text-base font-semibold ${liftColor(v.numerator_relative_lift)}`}
              >
                {liftFmt(v.numerator_relative_lift)}
              </div>
              {v.numerator_mean != null && (
                <div className="text-xs text-muted-foreground">
                  среднее: {v.numerator_mean.toFixed(4)}
                </div>
              )}
            </div>
            <div>
              <div className="mb-1 text-xs text-muted-foreground">└ Знаменатель</div>
              <div
                className={`text-base font-semibold ${liftColor(v.denominator_relative_lift)}`}
              >
                {liftFmt(v.denominator_relative_lift)}
              </div>
              {v.denominator_mean != null && (
                <div className="text-xs text-muted-foreground">
                  среднее: {v.denominator_mean.toFixed(4)}
                </div>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function DynamicsChart({ metricId, snapshots, treatmentVariants }) {
  const metricSnapshots = (snapshots || []).filter(
    (s) => s.metric_id === metricId && s.variant_name !== 'control',
  )
  if (metricSnapshots.length === 0) return null
  const dateMap = {}
  metricSnapshots.forEach((s) => {
    if (!dateMap[s.snapshot_date]) {
      dateMap[s.snapshot_date] = {
        date: s.snapshot_date,
        label: formatSnapshotDate(s.snapshot_date),
      }
    }
    if (s.p_value != null) {
      dateMap[s.snapshot_date][s.variant_name] = s.p_value
    }
  })
  const chartData = Object.values(dateMap).sort((a, b) =>
    a.date.localeCompare(b.date),
  )
  if (chartData.length < 2) return null
  return (
    <div className="mt-6">
      <h3 className="mb-1 text-sm font-semibold text-muted-foreground">
        📈 Динамика p-value
      </h3>
      <p className="mb-3 text-xs text-muted-foreground">
        Красная линия — порог значимости (p=0.05). Чем ниже линия — тем сильнее сигнал.
      </p>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={chartData} margin={{ top: 5, right: 15, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis
            domain={[0, 1]}
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => v.toFixed(2)}
          />
          <Tooltip
            formatter={(v, name) => [v != null ? v.toFixed(3) : '—', name]}
            labelFormatter={(label) => `Дата: ${label}`}
          />
          <Legend wrapperStyle={{ fontSize: '0.8rem' }} />
          <ReferenceLine
            y={0.05}
            stroke="#ef4444"
            strokeDasharray="6 3"
            label={{
              value: 'α=0.05',
              position: 'insideTopRight',
              fontSize: 10,
              fill: '#ef4444',
            }}
          />
          {treatmentVariants.map((varName, idx) => (
            <Line
              key={varName}
              type="monotone"
              dataKey={varName}
              stroke={LINE_COLORS[idx % LINE_COLORS.length]}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
              connectNulls
              strokeWidth={2}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function ExperimentResultsTab({
  experimentId,
  experimentStatus,
  isSequential = false,
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  const resultsQuery = useQuery({
    queryKey: ['experiment-results', experimentId],
    queryFn: async () => {
      try {
        const { data } = await getResults(experimentId)
        return data
      } catch {
        return null
      }
    },
  })

  const dailyQuery = useQuery({
    queryKey: ['experiment-daily', experimentId],
    queryFn: async () => {
      try {
        const { data } = await getDailyResults(experimentId)
        return data
      } catch {
        return null
      }
    },
  })

  const analyzeMutation = useMutation({
    mutationFn: () => analyzeExperiment(experimentId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['experiment-results', experimentId],
      })
      queryClient.invalidateQueries({
        queryKey: ['experiment-daily', experimentId],
      })
      toast({ description: t('experiments.results.analyzed') })
    },
    onError: (err) =>
      toast({
        variant: 'destructive',
        description: err.response?.data?.detail || t('errors.serverError'),
      }),
  })

  const results = resultsQuery.data
  const dailyResults = dailyQuery.data
  const insights = results?.insights ?? []

  return (
    <>
      {experimentStatus === 'running' && (
        <div className="mb-4 flex items-center justify-end">
          <Button
            onClick={() => analyzeMutation.mutate()}
            disabled={analyzeMutation.isLoading}
          >
            {analyzeMutation.isLoading
              ? t('common.loading')
              : t('experiments.results.analyze')}
          </Button>
        </div>
      )}

      {(resultsQuery.isLoading || dailyQuery.isLoading) && (
        <LoadingState variant="spinner" />
      )}

      {!resultsQuery.isLoading && !results && (
        <Alert variant="info" className="mb-4">
          <AlertDescription>
            {t('experiments.results.noResultsHint')}
          </AlertDescription>
        </Alert>
      )}

      {insights.length > 0 && (
        <div className="mb-4">
          <InsightPanel insights={insights} />
        </div>
      )}

      {isSequential && dailyResults?.snapshots && (
        <div className="mb-4">
          <SequentialPValueChart snapshots={dailyResults.snapshots} />
        </div>
      )}

      {results?.metrics?.map((metric) => {
        const treatmentVariants = (metric.variants || [])
          .filter((v) => v.variant_name !== 'control')
          .map((v) => v.variant_name)
        return (
          <Card key={metric.metric_id} className="mb-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                {metric.metric_name || t('experiments.create.metrics')}
                {metric.is_primary && (
                  <Badge variant="success">Primary</Badge>
                )}
                {metric.is_guardrail && (
                  <Badge variant="warning">Guardrail</Badge>
                )}
              </CardTitle>
              <div className="text-sm text-muted-foreground">
                {metric.metric_type}
              </div>
            </CardHeader>
            <CardContent>
              {metric.srm_detected && (
                <div className="mb-4">
                  <SRMAlert pValue={metric.srm_p_value} />
                </div>
              )}

              {metric.guardrail_violated && (
                <Alert variant="warning" className="mb-4">
                  <AlertDescription>
                    <strong>Guardrail нарушен</strong> — деплой не рекомендуется.
                  </AlertDescription>
                </Alert>
              )}

              <div className="mb-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs uppercase text-muted-foreground">
                      <th className="px-2 py-2">
                        {t('experiments.create.variants')}
                      </th>
                      <th className="px-2 py-2">N</th>
                      <th className="px-2 py-2">
                        {t('experiments.results.mean')}
                      </th>
                      <th className="px-2 py-2">Lift %</th>
                      <th className="px-2 py-2">p-value</th>
                      <th className="px-2 py-2">
                        {t('experiments.results.test')}
                      </th>
                      <th className="px-2 py-2">95% CI</th>
                      <th className="px-2 py-2">
                        {t('experiments.results.winner')}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {(metric.variants || []).map((v) => (
                      <tr
                        key={v.variant_id}
                        className={
                          v.is_winner
                            ? 'border-b bg-emerald-50 dark:bg-emerald-950/20'
                            : 'border-b'
                        }
                      >
                        <td className="px-2 py-2 font-medium">
                          {v.variant_name}
                        </td>
                        <td className="px-2 py-2">
                          {v.sample_size.toLocaleString()}
                        </td>
                        <td className="px-2 py-2">
                          {fmt(v.mean, metric.metric_type)}
                        </td>
                        <td className="px-2 py-2">
                          {v.relative_lift != null ? (
                            <span
                              className={
                                v.relative_lift >= 0
                                  ? 'font-medium text-emerald-600'
                                  : 'font-medium text-red-600'
                              }
                            >
                              {v.relative_lift >= 0 ? '+' : ''}
                              {v.relative_lift.toFixed(1)}%
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td className="px-2 py-2">
                          <SignificanceBadge pValue={v.p_value} />
                        </td>
                        <td className="px-2 py-2">
                          <TestBadgeWithNormality
                            testUsed={v.test_used}
                            isNormal={v.is_normal}
                          />
                        </td>
                        <td className="px-2 py-2 text-xs text-muted-foreground">
                          {v.ci_low != null
                            ? `[${fmt(v.ci_low, metric.metric_type)}, ${fmt(
                                v.ci_high,
                                metric.metric_type,
                              )}]`
                            : '—'}
                        </td>
                        <td className="px-2 py-2">
                          {v.is_winner ? (
                            <span className="font-bold text-emerald-600">🏆</span>
                          ) : (
                            '—'
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <AchievedMdeBlock metric={metric} />
              <DecompositionBlock variants={metric.variants} />

              <h3 className="mb-3 text-sm font-semibold text-muted-foreground">
                {t('experiments.results.compareVariants')}
              </h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart
                  data={(metric.variants || []).map((v) => ({
                    name: v.variant_name,
                    value:
                      v.mean != null
                        ? parseFloat(
                            (
                              v.mean *
                              (metric.metric_type === 'conversion' ? 100 : 1)
                            ).toFixed(4),
                          )
                        : 0,
                  }))}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip
                    formatter={(v) =>
                      metric.metric_type === 'conversion'
                        ? `${v.toFixed(2)}%`
                        : v
                    }
                  />
                  <Bar dataKey="value" fill="#4f46e5" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>

              {dailyResults && (
                <DynamicsChart
                  metricId={metric.metric_id}
                  snapshots={dailyResults.snapshots}
                  treatmentVariants={treatmentVariants}
                />
              )}

              {metric.variants.some((v) => v.ai_interpretation) && (
                <div className="mt-6">
                  <h3 className="mb-2 text-sm font-semibold text-muted-foreground">
                    🤖 AI интерпретация
                  </h3>
                  {metric.variants
                    .filter((v) => v.ai_interpretation)
                    .map((v) => (
                      <Alert key={v.variant_id} variant="info" className="mb-2">
                        <AlertDescription>
                          <strong>{v.variant_name}:</strong>{' '}
                          {v.ai_interpretation}
                        </AlertDescription>
                      </Alert>
                    ))}
                </div>
              )}
            </CardContent>
          </Card>
        )
      })}

      {results && results.metrics?.length === 0 && (
        <EmptyState
          title={t('common.noData')}
          description={t('experiments.results.noResults')}
        />
      )}
    </>
  )
}