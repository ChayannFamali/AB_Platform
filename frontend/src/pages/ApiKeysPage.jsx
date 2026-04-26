import { useEffect, useState } from 'react'
import { createApiKey, getApiKeys, revokeApiKey } from '../api/client'

export default function ApiKeysPage() {
  const [keys,       setKeys]       = useState([])
  const [newName,    setNewName]    = useState('')
  const [createdKey, setCreatedKey] = useState(null)
  const [loading,    setLoading]    = useState(true)
  const [creating,   setCreating]   = useState(false)
  const [error,      setError]      = useState('')

  const load = async () => {
    try {
      const { data } = await getApiKeys()
      setKeys(data)
    } catch { setError('Ошибка загрузки ключей') }
    finally   { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!newName.trim()) return
    setCreating(true)
    setCreatedKey(null)
    try {
      const { data } = await createApiKey({ name: newName.trim() })
      setCreatedKey(data.key)
      setNewName('')
      load()
    } catch (e) {
      setError(e.response?.data?.detail || 'Ошибка создания ключа')
    } finally { setCreating(false) }
  }

  const handleRevoke = async (id, name) => {
    if (!confirm(`Отозвать ключ "${name}"? Это действие необратимо.`)) return
    try {
      await revokeApiKey(id)
      setKeys(keys.filter(k => k.id !== id))
    } catch { setError('Ошибка отзыва ключа') }
  }

  if (loading) return <div className="loading">Загрузка...</div>

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">🔑 API Ключи</h1>
      </div>

      {/* Новый ключ — показываем ОДИН РАЗ */}
      {createdKey && (
        <div className="alert alert-success">
          <strong>Ключ создан!</strong> Скопируйте — он больше не будет показан полностью.
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginTop: '0.5rem' }}>
            <code style={{
              flex: 1, padding: '0.5rem', background: '#f0fdf4',
              borderRadius: '4px', fontSize: '0.82rem', wordBreak: 'break-all',
            }}>
              {createdKey}
            </code>
            <button className="btn btn-sm btn-secondary"
              onClick={() => navigator.clipboard.writeText(createdKey)}>
              📋 Копировать
            </button>
          </div>
          <button className="btn btn-sm btn-secondary"
            style={{ marginTop: '0.5rem' }}
            onClick={() => setCreatedKey(null)}>
            Закрыть
          </button>
        </div>
      )}

      {error && <div className="alert alert-danger">{error}</div>}

      {/* Создать новый ключ */}
      <div className="card">
        <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>
          Новый ключ
        </h2>
        <form onSubmit={handleCreate}>
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <input placeholder="Название (например: Production Backend)"
              value={newName} onChange={e => setNewName(e.target.value)}
              style={{ flex: 1 }} />
            <button type="submit" className="btn btn-primary" disabled={creating}>
              {creating ? 'Создание...' : '+ Создать'}
            </button>
          </div>
        </form>
      </div>

      {/* Список ключей */}
      <div className="card">
        <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>
          Ваши ключи
        </h2>
        {keys.length === 0 ? (
          <p className="text-muted">Нет ключей. Создайте первый.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Название</th>
                <th>Ключ</th>
                <th>Создан</th>
                <th>Последнее использование</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {keys.map(k => (
                <tr key={k.id}>
                  <td><strong>{k.name}</strong></td>
                  <td>
                    <code style={{ fontSize: '0.8rem', color: '#6b7280' }}>
                      {k.key_preview}
                    </code>
                  </td>
                  <td className="text-muted">
                    {new Date(k.created_at).toLocaleDateString('ru-RU')}
                  </td>
                  <td className="text-muted">
                    {k.last_used_at
                      ? new Date(k.last_used_at).toLocaleString('ru-RU')
                      : '—'}
                  </td>
                  <td>
                    <button className="btn btn-sm btn-danger"
                      onClick={() => handleRevoke(k.id, k.name)}>
                      Отозвать
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* SDK использование */}
      <div className="card">
        <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.75rem' }}>
          Использование в SDK
        </h2>
        <pre style={{
          background: '#1a1a2e', color: '#e2e8f0', padding: '1rem',
          borderRadius: '6px', fontSize: '0.8rem', overflowX: 'auto',
        }}>{`# Python SDK
from abplatform import ABPlatformClient
client = ABPlatformClient(
    api_url="http://your-server:8000",
    api_key="abp_ваш_ключ",
)

// JS SDK
const client = new ABPlatformClient({
  apiUrl: 'http://your-server:8000',
  apiKey: 'abp_ваш_ключ',
})`}
        </pre>
      </div>
    </>
  )
}
