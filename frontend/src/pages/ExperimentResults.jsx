import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
  LineChart, Line, Legend, ReferenceLine,
} from 'recharts'
import {
  getExperiment, analyzeExperiment,
  getResults, getDailyResults, updateStatus,
} from '../api/client'

// ─── Formatters ───────────────────────────────────────────────────────────────

const fmt = (v, type) => {
  if (v == null) return '—'
  if (type === 'conversion') return `${(v * 100).toFixed(2)}%`
  return v.toFixed(4)
}

const pFmt = (v) => {
  if (v == null) return '—'
  return v < 0.001 ? '<0.001' : v.toFixed(3)
}

const fmtMde = (mde, metricType) => {
  if (mde == null) return null
  if (metricType === 'conversion') return `${(mde * 100).toFixed(2)}%`
  return mde.toFixed(2)
}

// "2026-03-27" → "27.03" (timezone-safe)
const formatSnapshotDate = (dateStr) => {
  const parts = dateStr.split('-')
  return `${parts[2]}.${parts[1]}`
}

const LINE_COLORS = ['#4f46e5', '#059669', '#dc2626', '#d97706', '#7c3aed', '#0891b2']

// ─── Test badge ───────────────────────────────────────────────────────────────

const TEST_META = {
  mann_whitney: {
    label: 'Mann-Whitney',
    bg: '#fef3c7', color: '#92400e', border: '#fcd34d',
  },
  welch_t_test: {
    label: 'Welch t-test',
    bg: '#eff6ff', color: '#1e40af', border: '#93c5fd',
  },
  z_test: {
    label: 'Z-test',
    bg: '#eff6ff', color: '#1e40af', border: '#93c5fd',
  },
  delta_method: {                         
    label: 'Δ Delta method',
    bg: '#f0fdf4', color: '#166534', border: '#86efac',
  },
}

function TestBadge({ testUsed, isNormal }) {
  if (!testUsed) return <span className="text-muted">—</span>

  const meta = TEST_META[testUsed] ?? {
    label: testUsed, bg: '#f3f4f6', color: '#374151', border: '#d1d5db',
  }

  // Нормальность показываем только для параметрических тестов (не z_test, не delta)
  const showNormality = (testUsed === 'welch_t_test' || testUsed === 'mann_whitney')
    && isNormal !== null && isNormal !== undefined

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem', alignItems: 'flex-start' }}>
      <span style={{
        display: 'inline-block',
        padding: '0.15rem 0.45rem',
        borderRadius: '4px',
        fontSize: '0.7rem',
        fontWeight: 600,
        whiteSpace: 'nowrap',
        background: meta.bg,
        color: meta.color,
        border: `1px solid ${meta.border}`,
      }}>
        {meta.label}
      </span>

      {showNormality && (
        isNormal === false
          ? <span
              style={{ fontSize: '0.65rem', color: '#d97706', whiteSpace: 'nowrap', cursor: 'help' }}
              title="Shapiro-Wilk p < 0.05 — ненормальное распределение, применён непараметрический тест"
            >
              ⚠ Non-normal
            </span>
          : <span
              style={{ fontSize: '0.65rem', color: '#059669', whiteSpace: 'nowrap', cursor: 'help' }}
              title="Shapiro-Wilk: нормальное распределение"
            >
              ✓ Normal
            </span>
      )}
    </div>
  )
}

// ─── Achieved MDE block ───────────────────────────────────────────────────────

function AchievedMdeBlock({ metric }) {
  const targets = (metric.variants || []).filter(
    (v) => v.variant_name !== 'control'
      && v.is_significant === false
      && v.achieved_mde != null
  )
  if (targets.length === 0) return null

  return (
    <div className="alert alert-info" style={{ marginBottom: '1.5rem' }}>
      <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>
        📏 Чувствительность теста
      </div>
      <div style={{ fontSize: '0.825rem', color: '#1e3a5f', marginBottom: '0.5rem' }}>
        Результат незначим. При текущей выборке платформа обнаружила бы следующий минимальный эффект:
      </div>
      {targets.map((v) => {
        const mde = fmtMde(v.achieved_mde, metric.metric_type)
        if (!mde) return null
        return (
          <div key={v.variant_id} style={{ marginTop: '0.35rem', fontSize: '0.875rem' }}>
            <strong>{v.variant_name}</strong>
            <span className="text-muted"> (N={v.sample_size.toLocaleString()})</span>
            {' → '}
            видим эффект ≥ <strong style={{ color: '#1e40af' }}>{mde}</strong>
            {metric.metric_type === 'conversion' ? ' по конверсии' : ''}.
            Если реальный эффект меньше — увеличьте выборку или время эксперимента.
          </div>
        )
      })}
    </div>
  )
}

// ─── Decomposition block (ratio метрики) ─────────────────────────────────────

function DecompositionBlock({ variants }) {
  const withDecomp = (variants || []).filter(
    v => v.variant_name !== 'control' && v.numerator_relative_lift != null
  )
  if (withDecomp.length === 0) return null

  const liftColor = (val) => val == null ? '#9ca3af' : val >= 0 ? '#059669' : '#dc2626'
  const liftFmt   = (val) => val == null ? '—'
    : `${val >= 0 ? '+' : ''}${val.toFixed(1)}%`

  return (
    <div style={{ marginBottom: '1.5rem' }}>
      <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem', color: '#6b7280' }}>
        🔬 Декомпозиция эффекта
      </h3>
      <p style={{ fontSize: '0.75rem', color: '#9ca3af', marginBottom: '0.75rem' }}>
        Откуда взялся итоговый lift ratio метрики — из числителя, знаменателя или обоих.
      </p>
      {withDecomp.map((v) => (
        <div key={v.variant_id} style={{
          background: '#f9fafb',
          border: '1px solid #e5e7eb',
          borderRadius: '8px',
          padding: '0.875rem 1rem',
          marginBottom: '0.5rem',
        }}>
          <div style={{ fontWeight: 600, marginBottom: '0.6rem', fontSize: '0.875rem' }}>
            {v.variant_name}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem' }}>

            {/* Ratio (итог) */}
            <div>
              <div style={{ fontSize: '0.7rem', color: '#9ca3af', marginBottom: '0.2rem' }}>
                Ratio (итог)
              </div>
              <div style={{ fontSize: '1rem', fontWeight: 700, color: liftColor(v.relative_lift) }}>
                {liftFmt(v.relative_lift)}
              </div>
            </div>

            {/* Числитель */}
            <div>
              <div style={{ fontSize: '0.7rem', color: '#9ca3af', marginBottom: '0.2rem' }}>
                └ Числитель
              </div>
              <div style={{ fontSize: '1rem', fontWeight: 600, color: liftColor(v.numerator_relative_lift) }}>
                {liftFmt(v.numerator_relative_lift)}
              </div>
              {v.numerator_mean != null && (
                <div style={{ fontSize: '0.7rem', color: '#9ca3af' }}>
                  среднее: {v.numerator_mean.toFixed(4)}
                </div>
              )}
            </div>

            {/* Знаменатель */}
            <div>
              <div style={{ fontSize: '0.7rem', color: '#9ca3af', marginBottom: '0.2rem' }}>
                └ Знаменатель
              </div>
              <div style={{ fontSize: '1rem', fontWeight: 600, color: liftColor(v.denominator_relative_lift) }}>
                {liftFmt(v.denominator_relative_lift)}
              </div>
              {v.denominator_mean != null && (
                <div style={{ fontSize: '0.7rem', color: '#9ca3af' }}>
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

// ─── Dynamics chart (cumulative p-value) ─────────────────────────────────────

function DynamicsChart({ metricId, snapshots, treatmentVariants }) {
  const metricSnapshots = (snapshots || []).filter(
    s => s.metric_id === metricId && s.variant_name !== 'control'
  )
  if (metricSnapshots.length === 0) return null

  // Строим time series: { date, label, treatment_a: p_value, treatment_b: p_value, ... }
  const dateMap = {}
  metricSnapshots.forEach(s => {
    if (!dateMap[s.snapshot_date]) {
      dateMap[s.snapshot_date] = {
        date:  s.snapshot_date,
        label: formatSnapshotDate(s.snapshot_date),
      }
    }
    // p_value может быть null (контрол) — пропускаем
    if (s.p_value != null) {
      dateMap[s.snapshot_date][s.variant_name] = s.p_value
    }
  })

  const chartData = Object.values(dateMap)
    .sort((a, b) => a.date.localeCompare(b.date))

  // Нужно минимум 2 точки для осмысленного графика
  if (chartData.length < 2) return null

  return (
    <div style={{ marginTop: '1.5rem' }}>
      <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.25rem', color: '#6b7280' }}>
        📈 Динамика p-value
      </h3>
      <p style={{ fontSize: '0.75rem', color: '#9ca3af', marginBottom: '0.75rem' }}>
        Красная линия — порог значимости (p=0.05). Чем ниже линия — тем сильнее сигнал.
      </p>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={chartData} margin={{ top: 5, right: 15, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis
            domain={[0, 1]}
            tick={{ fontSize: 11 }}
            tickFormatter={v => v.toFixed(2)}
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
            label={{ value: 'α=0.05', position: 'insideTopRight', fontSize: 10, fill: '#ef4444' }}
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

// ─── Main component ───────────────────────────────────────────────────────────

export default function ExperimentResults() {
  const { id } = useParams()
  const [exp,          setExp]          = useState(null)
  const [results,      setResults]      = useState(null)
  const [dailyResults, setDailyResults] = useState(null)   // ← NEW v3
  const [loading,      setLoading]      = useState(true)
  const [analyzing,    setAnalyzing]    = useState(false)
  const [error,        setError]        = useState('')

  const load = async () => {
    try {
      const { data } = await getExperiment(id)
      setExp(data)

      // Текущие результаты
      try {
        const { data: r } = await getResults(id)
        setResults(r)
      } catch {
        setResults(null)
      }

      // Daily снапшоты (опционально — появляются после 01:00 UTC следующего дня)
      try {
        const { data: daily } = await getDailyResults(id)
        setDailyResults(daily)
      } catch {
        setDailyResults(null)  // 404 = нет данных ещё, это нормально
      }

    } catch {
      setError('Эксперимент не найден')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [id])

  const handleAnalyze = async () => {
    setAnalyzing(true)
    try {
      const { data } = await analyzeExperiment(id)
      setResults(data)
    } catch (e) {
      setError('Ошибка анализа: ' + (e.response?.data?.detail || e.message))
    } finally {
      setAnalyzing(false)
    }
  }

  const handleStatus = async (status) => {
    await updateStatus(id, status)
    load()
  }

  if (loading) return <div className="loading">Загрузка...</div>
  if (error)   return <div className="alert alert-danger">{error}</div>
  if (!exp)    return null

  return (
    <>
      {/* ── Header ── */}
      <div className="page-header">
        <div>
          <Link to="/" className="text-muted">← Все эксперименты</Link>
          <h1 className="page-title" style={{ marginTop: '0.25rem' }}>{exp.name}</h1>
          {exp.description && <p className="text-muted">{exp.description}</p>}
        </div>
        <div className="flex gap-1">
          <span className={`badge badge-${exp.status}`} style={{ fontSize: '0.85rem' }}>
            {exp.status}
          </span>
          {exp.status === 'draft' && (
            <button className="btn btn-success" onClick={() => handleStatus('running')}>
              ▶ Запустить
            </button>
          )}
          {exp.status === 'running' && (
            <button className="btn btn-secondary" onClick={() => handleStatus('paused')}>
              ⏸ Пауза
            </button>
          )}
          {(exp.status === 'running' || exp.status === 'paused') && (
            <button className="btn btn-primary" onClick={handleAnalyze} disabled={analyzing}>
              {analyzing ? '⏳ Анализируем...' : '🔍 Анализировать'}
            </button>
          )}
        </div>
      </div>

      {/* ── Info cards ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
        {[
          { label: 'Трафик',    value: `${exp.traffic_percentage}%` },
          { label: 'Вариантов', value: exp.variants.length },
          { label: 'Метрик',    value: exp.metrics.length },
        ].map(({ label, value }) => (
          <div key={label} className="card" style={{ textAlign: 'center', padding: '1rem', margin: 0 }}>
            <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>{value}</div>
            <div className="text-muted">{label}</div>
          </div>
        ))}
      </div>

      {/* ── No results yet ── */}
      {!results && (
        <div className="alert alert-info">
          Результатов пока нет.
          {exp.status === 'running'
            ? ' Нажмите «Анализировать» для запуска.'
            : ' Запустите эксперимент и соберите данные.'}
        </div>
      )}

      {/* ── Results ── */}
      {results && results.metrics.map((metric) => {
        const treatmentVariants = (metric.variants || [])
          .filter(v => v.variant_name !== 'control')
          .map(v => v.variant_name)

        return (
          <div key={metric.metric_id} className="card">

            {/* Metric header */}
            <div style={{ display: 'flex', justifyContent: 'space-between',
                          alignItems: 'center', marginBottom: '1rem' }}>
              <div>
                <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>
                  {metric.metric_name || 'Метрика'}
                  {metric.is_primary && (
                    <span className="badge badge-running" style={{ marginLeft: '0.5rem' }}>
                      Primary
                    </span>
                  )}
                  {metric.is_guardrail && (
                    <span className="badge badge-paused" style={{ marginLeft: '0.5rem' }}>
                      Guardrail
                    </span>
                  )}
                </h2>
                <span className="text-muted">{metric.metric_type}</span>
              </div>
            </div>

            {/* SRM Warning */}
            {metric.srm_detected && (
              <div className="alert alert-danger">
                <strong> Sample Ratio Mismatch обнаружен</strong> (p={pFmt(metric.srm_p_value)})
                <br />
                Соотношение пользователей отклонилось от ожидаемого.
                Результатам нельзя доверять до исправления проблемы в SDK.
              </div>
            )}

            {/* Guardrail violation */}
            {metric.guardrail_violated && (
              <div className="alert alert-warning">
                <strong> Guardrail метрика нарушена</strong> — деплой не рекомендуется.
              </div>
            )}

            {/* Results table */}
            <div style={{ overflowX: 'auto', marginBottom: '1rem' }}>
              <table style={{ minWidth: '820px', marginBottom: 0 }}>
                <thead>
                  <tr>
                    <th>Вариант</th>
                    <th>Выборка</th>
                    <th>Среднее</th>
                    <th>Эффект</th>
                    <th>Lift %</th>
                    <th>p-value</th>
                    <th>Тест</th>
                    <th>95% CI</th>
                    <th>Значимо</th>
                    <th>Победитель</th>
                  </tr>
                </thead>
                <tbody>
                  {(metric.variants || []).map((v) => (
                    <tr key={v.variant_id} className={v.is_winner ? 'winner-row' : ''}>
                      <td><strong>{v.variant_name}</strong></td>
                      <td>{v.sample_size.toLocaleString()}</td>
                      <td>{fmt(v.mean, metric.metric_type)}</td>
                      <td>
                        {v.effect_size != null
                          ? (v.effect_size >= 0 ? '+' : '') + fmt(v.effect_size, metric.metric_type)
                          : '—'}
                      </td>
                      <td>
                        {v.relative_lift != null
                          ? <span style={{
                              color: v.relative_lift >= 0 ? '#059669' : '#dc2626',
                              fontWeight: 500,
                            }}>
                              {v.relative_lift >= 0 ? '+' : ''}{v.relative_lift.toFixed(1)}%
                            </span>
                          : '—'}
                      </td>
                      <td>{pFmt(v.p_value)}</td>
                      <td>
                        <TestBadge testUsed={v.test_used} isNormal={v.is_normal} />
                      </td>
                      <td style={{ fontSize: '0.8rem', color: '#6b7280', whiteSpace: 'nowrap' }}>
                        {v.ci_low != null
                          ? `[${fmt(v.ci_low, metric.metric_type)}, ${fmt(v.ci_high, metric.metric_type)}]`
                          : '—'}
                      </td>
                      <td>
                        {v.is_significant === null ? '—'
                          : v.is_significant
                            ? <span style={{ color: '#059669', fontWeight: 600 }}>✓ Да</span>
                            : <span style={{ color: '#9ca3af' }}>Нет</span>}
                      </td>
                      <td>
                        {v.is_winner
                          ? <span style={{ color: '#059669', fontWeight: 700 }}>🏆 Да</span>
                          : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Achieved MDE */}
            <AchievedMdeBlock metric={metric} />

            {/* Decomposition (только для ratio метрик) */}
            <DecompositionBlock variants={metric.variants} />

            {/* Bar chart: сравнение вариантов */}
            <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.75rem', color: '#6b7280' }}>
              Сравнение вариантов
            </h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={(metric.variants || []).map(v => ({
                name: v.variant_name,
                value: v.mean != null
                  ? parseFloat((v.mean * (metric.metric_type === 'conversion' ? 100 : 1)).toFixed(4))
                  : 0,
              }))}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip
                  formatter={(v) => metric.metric_type === 'conversion' ? `${v.toFixed(2)}%` : v}
                />
                <Bar dataKey="value" fill="#4f46e5" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>

            {/* Dynamics chart (если есть daily данные) */}
            {dailyResults && (
              <DynamicsChart
                metricId={metric.metric_id}
                snapshots={dailyResults.snapshots}
                treatmentVariants={treatmentVariants}
              />
            )}

            {/* AI interpretation */}
            {metric.variants.some(v => v.ai_interpretation) && (
              <div style={{ marginTop: '1.5rem' }}>
                <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem', color: '#6b7280' }}>
                  🤖 AI интерпретация
                </h3>
                {metric.variants.filter(v => v.ai_interpretation).map(v => (
                  <div key={v.variant_id} className="alert alert-info">
                    <strong>{v.variant_name}:</strong> {v.ai_interpretation}
                  </div>
                ))}
              </div>
            )}

          </div>
        )
      })}
    </>
  )
}
