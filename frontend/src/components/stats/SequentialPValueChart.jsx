import { useTranslation } from 'react-i18next'
import {
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

import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'

/**
 * Time-series chart of always-valid p-value (mSPRT) across daily snapshots.
 *
 * Only shown for sequential experiments — non-sequential experiments
 * render a single fixed-horizon p-value, not a trajectory.
 */
export default function SequentialPValueChart({ snapshots, alpha = 0.05 }) {
  const { t } = useTranslation()
  if (!snapshots || snapshots.length === 0) return null

  // Group by metric + variant so each line is one (metric, variant) trajectory.
  const seriesMap = new Map()
  for (const s of snapshots) {
    const key = `${s.metric_name} · ${s.variant_name}`
    if (s.sequential_fpr == null) continue
    if (!seriesMap.has(key)) seriesMap.set(key, [])
    seriesMap.get(key).push({
      date: s.snapshot_date,
      fpr: s.sequential_fpr,
    })
  }

  // Merge all dates into a single sorted x-axis and align each series.
  const allDates = [
    ...new Set(snapshots.map((s) => s.snapshot_date)),
  ].sort()
  const series = [...seriesMap.entries()].map(([name, points]) => {
    const byDate = new Map(points.map((p) => [p.date, p.fpr]))
    return {
      name,
      data: allDates.map((d) => ({
        date: d,
        fpr: byDate.get(d) ?? null,
      })),
    }
  })

  const chartData = allDates.map((d) => {
    const row = { date: d }
    for (const s of series) {
      const point = s.data.find((p) => p.date === d)
      row[s.name] = point?.fpr ?? null
    }
    return row
  })

  const colors = ['#10b981', '#3b82f6', '#f59e0b', '#ec4899', '#8b5cf6']

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">
          {t('stats.sequential.chartTitle')}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chartData}
              margin={{ top: 8, right: 16, bottom: 8, left: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis
                dataKey="date"
                tickFormatter={(d) => (typeof d === 'string' ? d : d.toString())}
                fontSize={12}
              />
              <YAxis
                domain={[0, 1]}
                tickFormatter={(v) => v.toFixed(1)}
                fontSize={12}
              />
              <ReferenceLine
                y={alpha}
                stroke="#ef4444"
                strokeDasharray="4 4"
                label={{
                  value: `α = ${alpha}`,
                  fill: '#ef4444',
                  fontSize: 11,
                  position: 'right',
                }}
              />
              <Tooltip
                formatter={(v) => (v == null ? '—' : v.toFixed(4))}
                labelFormatter={(l) => `Date: ${l}`}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {series.map((s, i) => (
                <Line
                  key={s.name}
                  type="monotone"
                  dataKey={s.name}
                  stroke={colors[i % colors.length]}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          {t('stats.sequential.chartHelp')}
        </p>
      </CardContent>
    </Card>
  )
}