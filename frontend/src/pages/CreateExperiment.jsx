import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createExperiment, getSampleSizeConversion } from '../api/client'

const DEFAULT_METRIC = {
  name: '',
  event_name: '',
  denominator_event_name: null,   // ← NEW v3: для ratio метрик
  metric_type: 'conversion',
  is_primary: true,
  is_guardrail: false,
}

const DEFAULT_FORM = {
  name: '',
  description: '',
  traffic_percentage: 100,
  variants: [
    { name: 'control',   traffic_split: 50 },
    { name: 'treatment', traffic_split: 50 },
  ],
  metrics: [{ ...DEFAULT_METRIC }],
}

export default function CreateExperiment() {
  const [form, setForm]             = useState(DEFAULT_FORM)
  const [sampleSize, setSampleSize] = useState(null)
  const [calc, setCalc]             = useState({ baseline_rate: '', mde: '', daily_traffic: '' })
  const [calcError, setCalcError]   = useState('')
  const [error, setError]           = useState('')
  const [loading, setLoading]       = useState(false)
  const navigate = useNavigate()

  const updateMetric = (i, field, value) => {
    const metrics = [...form.metrics]
    let updated = { ...metrics[i], [field]: value }
    // Сбросить denominator при переключении на conversion
    if (field === 'metric_type' && value === 'conversion') {
      updated.denominator_event_name = null
    }
    metrics[i] = updated
    setForm({ ...form, metrics })
  }

  const addMetric = () => setForm({
    ...form,
    metrics: [...form.metrics, { ...DEFAULT_METRIC, is_primary: false }],
  })

  const removeMetric = (i) => setForm({
    ...form,
    metrics: form.metrics.filter((_, idx) => idx !== i),
  })

  const calcSampleSize = async () => {
    setCalcError('')
    setSampleSize(null)

    const baselineRate = parseFloat(calc.baseline_rate)
    const mde          = parseFloat(calc.mde)

    if (!calc.baseline_rate || !calc.mde) {
      setCalcError('Заполните базовую конверсию и MDE.')
      return
    }
    if (isNaN(baselineRate) || isNaN(mde)) {
      setCalcError('Введите числовые значения.')
      return
    }
    if (baselineRate <= 0 || baselineRate >= 1) {
      const suggestion = (baselineRate / 100).toFixed(4)
      setCalcError(
        `Базовая конверсия должна быть от 0 до 1. ` +
        `Вы ввели ${baselineRate} — имели в виду ${suggestion}? ` +
        `(${baselineRate}% → ${suggestion})`
      )
      return
    }
    if (mde <= 0 || mde >= 1) {
      const suggestion = (mde / 100).toFixed(4)
      setCalcError(
        `MDE должен быть от 0 до 1. ` +
        `Вы ввели ${mde} — имели в виду ${suggestion}? ` +
        `(${mde}% → ${suggestion})`
      )
      return
    }
    if (baselineRate + mde > 1) {
      setCalcError(
        `baseline_rate + MDE = ${(baselineRate + mde).toFixed(3)} > 1. ` +
        `Уменьшите одно из значений.`
      )
      return
    }

    try {
      const { data } = await getSampleSizeConversion({
        baseline_rate: baselineRate,
        mde:           mde,
        daily_traffic: calc.daily_traffic ? parseInt(calc.daily_traffic) : undefined,
      })
      setSampleSize(data)
    } catch (e) {
      const detail = e.response?.data?.detail
      const msg = Array.isArray(detail)
        ? detail.map(d => d.msg).join(', ')
        : (detail || 'Ошибка расчёта. Проверьте введённые значения.')
      setCalcError(msg)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { data } = await createExperiment({
        ...form,
        traffic_percentage: Number(form.traffic_percentage),
        variants: form.variants.map(v => ({ ...v, traffic_split: Number(v.traffic_split) })),
        metrics: form.metrics.map(m => ({
          ...m,
          // Пустая строка → null, чтобы бэкенд не получил ""
          denominator_event_name: m.denominator_event_name || null,
        })),
      })
      navigate(`/experiments/${data.id}`)
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка создания')
    } finally {
      setLoading(false)
    }
  }

  const isRatioType = (type) => type === 'revenue' || type === 'duration'

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Новый эксперимент</h1>
      </div>

      {/* ── Калькулятор выборки ── */}
      <div className="card">
        <h2 style={{ marginBottom: '1rem', fontSize: '1rem', fontWeight: 600 }}>
          📊 Калькулятор размера выборки
        </h2>
        <div className="form-row">
          <div className="form-group">
            <label>Текущая конверсия</label>
            <input type="number" step="0.001" placeholder="0.032"
              value={calc.baseline_rate}
              onChange={e => setCalc({ ...calc, baseline_rate: e.target.value })} />
            <p className="form-hint">Пример: 0.032 = 3.2%</p>
          </div>
          <div className="form-group">
            <label>Минимальный эффект (MDE)</label>
            <input type="number" step="0.001" placeholder="0.005"
              value={calc.mde}
              onChange={e => setCalc({ ...calc, mde: e.target.value })} />
            <p className="form-hint">Пример: 0.005 = +0.5%</p>
          </div>
        </div>
        <div className="form-group">
          <label>Дневной трафик (опционально)</label>
          <input type="number" placeholder="500"
            value={calc.daily_traffic}
            onChange={e => setCalc({ ...calc, daily_traffic: e.target.value })} />
        </div>
        <button className="btn btn-secondary" onClick={calcSampleSize}>
          Рассчитать
        </button>

        {calcError && (
          <div className="alert alert-warning mt-1" style={{ marginTop: '0.75rem' }}>
             {calcError}
          </div>
        )}

        {sampleSize && (
          <div className="alert alert-info mt-2">
            <strong>На вариант:</strong> {sampleSize.sample_size_per_variant.toLocaleString()} пользователей
            &nbsp;·&nbsp;
            <strong>Всего:</strong> {sampleSize.total_sample_size.toLocaleString()}
            {sampleSize.days_needed && (
              <span>&nbsp;·&nbsp;<strong>Дней:</strong> {sampleSize.days_needed}</span>
            )}
          </div>
        )}
      </div>

      {/* ── Форма эксперимента ── */}
      <form onSubmit={handleSubmit}>
        {error && <div className="alert alert-danger">{error}</div>}

        {/* Основное */}
        <div className="card">
          <h2 style={{ marginBottom: '1rem', fontSize: '1rem', fontWeight: 600 }}>Основное</h2>
          <div className="form-group">
            <label>Название *</label>
            <input required placeholder="Тест цвета кнопки"
              value={form.name}
              onChange={e => setForm({ ...form, name: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Описание</label>
            <textarea rows={2} placeholder="Что тестируем и зачем"
              value={form.description}
              onChange={e => setForm({ ...form, description: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Трафик (%)</label>
            <input type="number" min={1} max={100}
              value={form.traffic_percentage}
              onChange={e => setForm({ ...form, traffic_percentage: e.target.value })} />
            <p className="form-hint">Какой % всех пользователей участвует в эксперименте</p>
          </div>
        </div>

        {/* Варианты */}
        <div className="card">
          <h2 style={{ marginBottom: '1rem', fontSize: '1rem', fontWeight: 600 }}>Варианты</h2>
          {form.variants.map((v, i) => (
            <div key={i} className="form-row" style={{ marginBottom: '0.75rem' }}>
              <div className="form-group" style={{ margin: 0 }}>
                <label>Название</label>
                <input value={v.name}
                  onChange={e => {
                    const variants = [...form.variants]
                    variants[i] = { ...variants[i], name: e.target.value }
                    setForm({ ...form, variants })
                  }} />
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label>Трафик (%)</label>
                <input type="number" min={1} max={100} value={v.traffic_split}
                  onChange={e => {
                    const variants = [...form.variants]
                    variants[i] = { ...variants[i], traffic_split: e.target.value }
                    setForm({ ...form, variants })
                  }} />
              </div>
            </div>
          ))}
          <p className="form-hint">Сумма трафика вариантов должна быть 100%</p>
        </div>

        {/* Метрики */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
            <h2 style={{ fontSize: '1rem', fontWeight: 600 }}>Метрики</h2>
            <button type="button" className="btn btn-sm btn-secondary" onClick={addMetric}>
              + Добавить метрику
            </button>
          </div>

          {form.metrics.map((m, i) => (
            <div key={i} style={{
              borderTop: i > 0 ? '1px solid #f3f4f6' : 'none',
              paddingTop: i > 0 ? '1rem' : 0,
              marginBottom: '1rem',
            }}>

              {/* Название + тип */}
              <div className="form-row">
                <div className="form-group">
                  <label>Название метрики *</label>
                  <input required placeholder="Клик по кнопке"
                    value={m.name}
                    onChange={e => updateMetric(i, 'name', e.target.value)} />
                </div>
                <div className="form-group">
                  <label>Тип</label>
                  <select value={m.metric_type}
                    onChange={e => updateMetric(i, 'metric_type', e.target.value)}>
                    <option value="conversion">Конверсия</option>
                    <option value="revenue">Выручка</option>
                    <option value="duration">Длительность</option>
                  </select>
                </div>
              </div>

              {/* Event name + denominator */}
              <div className="form-row">
                <div className="form-group">
                  <label>Event name (числитель) *</label>
                  <input required placeholder="button_click"
                    value={m.event_name}
                    onChange={e => updateMetric(i, 'event_name', e.target.value)} />
                  <p className="form-hint">
                    {isRatioType(m.metric_type)
                      ? 'Числитель: какое событие суммируем'
                      : 'Какое событие отслеживаем'}
                  </p>
                </div>

                {/*Denominator field (только для revenue/duration)  */}
                {isRatioType(m.metric_type) && (
                  <div className="form-group">
                    <label>
                      Знаменатель event{' '}
                      <span className="text-muted" style={{ fontWeight: 400 }}>(для ratio)</span>
                    </label>
                    <input
                      placeholder="session_start"
                      value={m.denominator_event_name || ''}
                      onChange={e => updateMetric(i, 'denominator_event_name', e.target.value || null)}
                    />
                    <p className="form-hint">
                      {m.denominator_event_name
                        ? `→ ratio метрика: sum(${m.event_name || '...'}) / sum(${m.denominator_event_name})`
                        : 'Оставьте пустым для обычной revenue/duration метрики'}
                    </p>
                  </div>
                )}
              </div>

              {/* Ratio badge */}
              {isRatioType(m.metric_type) && m.denominator_event_name && (
                <div style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  padding: '0.25rem 0.6rem',
                  background: '#f0fdf4',
                  border: '1px solid #86efac',
                  borderRadius: '6px',
                  fontSize: '0.75rem',
                  color: '#166534',
                  marginBottom: '0.75rem',
                }}>
                  <span>Δ</span>
                  <strong>Ratio метрика</strong> — будет применён Delta method (корректный тест для ratio)
                </div>
              )}

              {/* Флаги + удаление */}
              <div className="form-group" style={{ display: 'flex', gap: '1.5rem', alignItems: 'center' }}>
                <label style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', cursor: 'pointer' }}>
                  <input type="checkbox" checked={m.is_primary}
                    onChange={e => updateMetric(i, 'is_primary', e.target.checked)} />
                  Primary
                </label>
                <label style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', cursor: 'pointer' }}>
                  <input type="checkbox" checked={m.is_guardrail}
                    onChange={e => updateMetric(i, 'is_guardrail', e.target.checked)} />
                  Guardrail
                </label>
                {form.metrics.length > 1 && (
                  <button type="button" className="btn btn-sm btn-danger"
                    onClick={() => removeMetric(i)}>
                    Удалить
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>

        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? 'Создание...' : 'Создать эксперимент'}
        </button>
      </form>
    </>
  )
}
