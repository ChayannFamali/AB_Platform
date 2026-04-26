import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { deleteExperiment, getExperiments, updateStatus } from '../api/client'

const STATUS_LABELS = {
  draft: 'Draft', running: 'Running',
  paused: 'Paused', completed: 'Completed',
}

const LIMIT = 20

export default function ExperimentList() {
  const [experiments,  setExperiments]  = useState([])
  const [total,        setTotal]        = useState(0)
  const [offset,       setOffset]       = useState(0)
  const [statusFilter, setStatusFilter] = useState('')
  const [loading,      setLoading]      = useState(true)

  const load = async (newOffset = 0, newStatus = statusFilter) => {
    setLoading(true)
    try {
      const { data } = await getExperiments({
        limit:  LIMIT,
        offset: newOffset,
        ...(newStatus ? { status: newStatus } : {}),
      })
      setExperiments(data.items)
      setTotal(data.total)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(0, '') }, [])

  const handleStatusFilter = (s) => {
    setStatusFilter(s)
    setOffset(0)
    load(0, s)
  }

  const handlePrev = () => {
    const o = Math.max(0, offset - LIMIT)
    setOffset(o)
    load(o)
  }

  const handleNext = () => {
    const o = offset + LIMIT
    setOffset(o)
    load(o)
  }

  const handleStatus = async (id, status) => {
    await updateStatus(id, status)
    load(offset)
  }

  const handleDelete = async (id) => {
    if (!confirm('Удалить эксперимент?')) return
    await deleteExperiment(id)
    // Если удалили последний на странице — вернуться на предыдущую
    const newOffset = experiments.length === 1 && offset > 0
      ? offset - LIMIT : offset
    setOffset(newOffset)
    load(newOffset)
  }

  // Вычисляем навигацию
  const from       = total === 0 ? 0 : offset + 1
  const to         = Math.min(offset + LIMIT, total)
  const totalPages = Math.ceil(total / LIMIT) || 1
  const currentPage= Math.floor(offset / LIMIT) + 1

  return (
    <>
      {/* ── Header ── */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Эксперименты</h1>
          {!loading && (
            <p className="text-muted" style={{ marginTop: '0.25rem' }}>
              Всего: {total}
            </p>
          )}
        </div>
        <Link to="/experiments/new" className="btn btn-primary">+ Создать</Link>
      </div>

      {/* ── Фильтр по статусу ── */}
      <div style={{ marginBottom: '1rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        {['', 'draft', 'running', 'paused', 'completed'].map((s) => (
          <button
            key={s}
            onClick={() => handleStatusFilter(s)}
            className="btn btn-sm"
            style={{
              background: statusFilter === s ? '#4f46e5' : '#e5e7eb',
              color:      statusFilter === s ? '#fff'    : '#374151',
            }}
          >
            {s === '' ? 'Все' : STATUS_LABELS[s]}
          </button>
        ))}
      </div>

      {/* ── Таблица ── */}
      {loading ? (
        <div className="loading">Загрузка...</div>
      ) : experiments.length === 0 ? (
        <div className="card text-center">
          <p className="text-muted">
            {statusFilter
              ? `Нет экспериментов со статусом «${STATUS_LABELS[statusFilter]}»`
              : 'Нет экспериментов. Создайте первый!'}
          </p>
        </div>
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Название</th>
                <th>Статус</th>
                <th>Трафик</th>
                <th>Создан</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {experiments.map((exp) => (
                <tr key={exp.id}>
                  <td>
                    <Link
                      to={`/experiments/${exp.id}`}
                      style={{ color: '#4f46e5', fontWeight: 500 }}
                    >
                      {exp.name}
                    </Link>
                  </td>
                  <td>
                    <span className={`badge badge-${exp.status}`}>
                      {STATUS_LABELS[exp.status]}
                    </span>
                  </td>
                  <td>{exp.traffic_percentage}%</td>
                  <td className="text-muted">
                    {new Date(exp.created_at).toLocaleDateString('ru-RU')}
                  </td>
                  <td>
                    <div className="flex gap-1">
                      <Link to={`/experiments/${exp.id}`} className="btn btn-sm btn-secondary">
                        Открыть
                      </Link>
                      {exp.status === 'draft' && (
                        <button className="btn btn-sm btn-success"
                          onClick={() => handleStatus(exp.id, 'running')}>
                          ▶ Запустить
                        </button>
                      )}
                      {exp.status === 'running' && (
                        <button className="btn btn-sm btn-secondary"
                          onClick={() => handleStatus(exp.id, 'paused')}>
                          ⏸ Пауза
                        </button>
                      )}
                      {exp.status === 'draft' && (
                        <button className="btn btn-sm btn-danger"
                          onClick={() => handleDelete(exp.id)}>
                          🗑
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* ── Пагинация ── */}
          {total > LIMIT && (
            <div className="pagination">
              <button
                className="btn btn-sm btn-secondary"
                onClick={handlePrev}
                disabled={offset === 0}
              >
                ← Назад
              </button>

              <span className="pagination-info">
                {from}–{to} из {total} · страница {currentPage} из {totalPages}
              </span>

              <button
                className="btn btn-sm btn-secondary"
                onClick={handleNext}
                disabled={offset + LIMIT >= total}
              >
                Вперёд →
              </button>
            </div>
          )}
        </div>
      )}
    </>
  )
}
