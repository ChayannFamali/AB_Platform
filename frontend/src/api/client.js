import axios from 'axios'

const api = axios.create({ baseURL: '' })

// ─── Interceptors ─────────────────────────────────────────────────────────────

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const path = window.location.pathname
      if (path !== '/login' && path !== '/register') {
        localStorage.removeItem('access_token')
        localStorage.removeItem('user')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

// ─── Auth ────────────────────────────────────────────────────────────────────
export const register = (data) => api.post('/api/v1/auth/register', data)
export const login    = (data) => api.post('/api/v1/auth/login', data)
export const getMe    = ()     => api.get('/api/v1/auth/me')

// ─── API Keys ─────────────────────────────────────────────────────────────────
export const getApiKeys   = ()     => api.get('/api/v1/api-keys')
export const createApiKey = (data) => api.post('/api/v1/api-keys', data)
export const revokeApiKey = (id)   => api.delete(`/api/v1/api-keys/${id}`)

// ─── Experiments ──────────────────────────────────────────────────────────────
export const getExperiments = (params = {}) => api.get('/api/v1/experiments', { params })
export const getExperiment    = (id)    => api.get(`/api/v1/experiments/${id}`)
export const createExperiment = (data)  => api.post('/api/v1/experiments', data)
export const updateStatus     = (id, s) => api.patch(`/api/v1/experiments/${id}/status`, { status: s })
export const deleteExperiment = (id)    => api.delete(`/api/v1/experiments/${id}`)

// ─── Analysis ────────────────────────────────────────────────────────────────
export const analyzeExperiment = (id) => api.post(`/api/v1/experiments/${id}/analyze`)
export const getResults        = (id) => api.get(`/api/v1/experiments/${id}/results`)
export const getDailyResults   = (id) =>
  api.get(`/api/v1/experiments/${id}/results/daily`)

// ─── CSV export (M-005) ──────────────────────────────────────────────────────
// Returns a Blob so the ExportButton can trigger a file download. The
// response interceptor skips the JSON parse — we want raw text/csv bytes.
export const exportResults = (id) =>
  api.get(`/api/v1/experiments/${id}/results/export?format=csv`, {
    responseType: 'blob',
  })

// ─── Sample Size ──────────────────────────────────────────────────────────────
export const getSampleSizeConversion = (p) =>
  api.get('/api/v1/stats/sample-size/conversion', { params: p })
export const getSampleSizeContinuous = (p) =>
  api.get('/api/v1/stats/sample-size/revenue', { params: p })

// ─── Users & Roles (M-003) + Audit Log (M-004) ───────────────────────────────
export const getUsers       = (params = {}) => api.get('/api/v1/users',   { params })
export const getRoles       = ()              => api.get('/api/v1/roles')
export const assignRole     = (userId, roleId) =>
  api.post(`/api/v1/users/${userId}/roles`, { role_id: roleId })
export const revokeRole     = (userId, roleId) =>
  api.delete(`/api/v1/users/${userId}/roles/${roleId}`)
export const updateUserActive = (userId, isActive) =>
  api.patch(`/api/v1/users/${userId}`, { is_active: isActive })

export const getAuditLog    = (params = {}) => api.get('/api/v1/audit', { params })

// ─── Feature Flags (M-009) ──────────────────────────────────────────────────
export const getFlags = (params = {}) =>
  api.get('/api/v1/flags', { params }).then((r) => r.data)

export const getFlag = (id) =>
  api.get(`/api/v1/flags/${id}`).then((r) => r.data)

export const getFlagByKey = (key) =>
  api.get(`/api/v1/flags/by-key/${key}`).then((r) => r.data)

export const createFlag = (data) =>
  api.post('/api/v1/flags', data).then((r) => r.data)

export const updateFlag = (id, data) =>
  api.patch(`/api/v1/flags/${id}`, data).then((r) => r.data)

export const toggleFlag = (id, enabled) =>
  api.patch(`/api/v1/flags/${id}/toggle`, { enabled }).then((r) => r.data)

export const deleteFlag = (id) =>
  api.delete(`/api/v1/flags/${id}`).then((r) => r.data)

export const addFlagRule = (id, data) =>
  api.post(`/api/v1/flags/${id}/rules`, data).then((r) => r.data)

export const deleteFlagRule = (flagId, ruleId) =>
  api.delete(`/api/v1/flags/${flagId}/rules/${ruleId}`).then((r) => r.data)

export const getFlagSummary = () =>
  api.get('/api/v1/flags/summary').then((r) => r.data)
