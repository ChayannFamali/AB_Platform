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
export const getDailyResults = (id) =>
  api.get(`/experiments/${id}/results/daily`)
// ─── Sample Size ──────────────────────────────────────────────────────────────
export const getSampleSizeConversion = (p) =>
  api.get('/api/v1/stats/sample-size/conversion', { params: p })
