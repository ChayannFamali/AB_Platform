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

// ─── Segments (M-010) ──────────────────────────────────────────────────────
// Targeting definitions reusable across flags and experiments. Rules
// inside a segment are AND-combined; user_properties is the matching
// input (passed by the SDK at evaluate time).
export const getSegments = (params = {}) =>
  api.get('/api/v1/segments', { params }).then((r) => r.data)

export const getSegment = (id) =>
  api.get(`/api/v1/segments/${id}`).then((r) => r.data)

export const getSegmentByKey = (key) =>
  api.get(`/api/v1/segments/by-key/${key}`).then((r) => r.data)

export const createSegment = (data) =>
  api.post('/api/v1/segments', data).then((r) => r.data)

export const updateSegment = (id, data) =>
  api.patch(`/api/v1/segments/${id}`, data).then((r) => r.data)

export const deleteSegment = (id) =>
  api.delete(`/api/v1/segments/${id}`).then((r) => r.data)

export const addSegmentRule = (id, data) =>
  api.post(`/api/v1/segments/${id}/rules`, data).then((r) => r.data)

export const deleteSegmentRule = (segmentId, ruleId) =>
  api.delete(`/api/v1/segments/${segmentId}/rules/${ruleId}`).then((r) => r.data)

// Dry-run a segment against a hypothetical user_properties payload.
export const evaluateSegment = (id, userProperties) =>
  api
    .post(`/api/v1/segments/${id}/evaluate`, { user_properties: userProperties })
    .then((r) => r.data)

// M2M linking: attach a segment to one or more experiments.
export const linkSegmentToExperiments = (id, experimentIds) =>
  api
    .post(`/api/v1/segments/${id}/experiments`, { experiment_ids: experimentIds })
    .then((r) => r.data)

export const unlinkSegmentFromExperiment = (id, experimentId) =>
  api
    .delete(`/api/v1/segments/${id}/experiments/${experimentId}`)
    .then((r) => r.data)

// ─── Holdouts (M-010) ──────────────────────────────────────────────────────
// Long-term measurement baselines. A deterministic fraction of users
// (size_pct) is excluded from linked experiments so analysts can compare
// outcomes against a never-exposed cohort.
export const getHoldouts = (params = {}) =>
  api.get('/api/v1/holdouts', { params }).then((r) => r.data)

export const getHoldout = (id) =>
  api.get(`/api/v1/holdouts/${id}`).then((r) => r.data)

export const getHoldoutByKey = (key) =>
  api.get(`/api/v1/holdouts/by-key/${key}`).then((r) => r.data)

export const createHoldout = (data) =>
  api.post('/api/v1/holdouts', data).then((r) => r.data)

export const updateHoldout = (id, data) =>
  api.patch(`/api/v1/holdouts/${id}`, data).then((r) => r.data)

export const deleteHoldout = (id) =>
  api.delete(`/api/v1/holdouts/${id}`).then((r) => r.data)

export const getHoldoutExclusions = (id, params = {}) =>
  api.get(`/api/v1/holdouts/${id}/exclusions`, { params }).then((r) => r.data)

export const addHoldoutExclusion = (id, data) =>
  api.post(`/api/v1/holdouts/${id}/exclusions`, data).then((r) => r.data)

export const removeHoldoutExclusion = (id, userId) =>
  api.delete(`/api/v1/holdouts/${id}/exclusions/${userId}`).then((r) => r.data)

// ─── Custom Metrics (M-011) ─────────────────────────────────────────────────
// Reusable metric templates. A CustomMetric encodes "what to measure"
// once and is snapshotted into a per-experiment Metric row at
// experiment-creation time. Editing a template does NOT mutate existing
// experiment metrics — they are immutable snapshots.
export const getCustomMetrics = (params = {}) =>
  api.get('/api/v1/custom-metrics', { params }).then((r) => r.data)

export const getCustomMetric = (id) =>
  api.get(`/api/v1/custom-metrics/${id}`).then((r) => r.data)

export const getCustomMetricByKey = (key) =>
  api.get(`/api/v1/custom-metrics/by-key/${key}`).then((r) => r.data)

export const createCustomMetric = (data) =>
  api.post('/api/v1/custom-metrics', data).then((r) => r.data)

export const updateCustomMetric = (id, data) =>
  api.patch(`/api/v1/custom-metrics/${id}`, data).then((r) => r.data)

export const deleteCustomMetric = (id) =>
  api.delete(`/api/v1/custom-metrics/${id}`).then((r) => r.data)

// Dry-run a custom metric against a hypothetical user_properties payload.
export const previewCustomMetric = (id, userProperties) =>
  api
    .post(`/api/v1/custom-metrics/${id}/preview`, { user_properties: userProperties })
    .then((r) => r.data)

// ─── Guardrails (M-011) ──────────────────────────────────────────────────────
// Per-experiment thresholds that fire (warning) or block (critical)
// variants when treatment crosses the configured lift. Nested under
// experiments so the URL carries the experiment_id naturally.
export const getGuardrails = (experimentId, params = {}) =>
  api
    .get(`/api/v1/experiments/${experimentId}/guardrails`, { params })
    .then((r) => r.data)

export const createGuardrail = (experimentId, data) =>
  api
    .post(`/api/v1/experiments/${experimentId}/guardrails`, data)
    .then((r) => r.data)

export const updateGuardrail = (experimentId, guardrailId, data) =>
  api
    .patch(
      `/api/v1/experiments/${experimentId}/guardrails/${guardrailId}`,
      data,
    )
    .then((r) => r.data)

export const deleteGuardrail = (experimentId, guardrailId) =>
  api
    .delete(`/api/v1/experiments/${experimentId}/guardrails/${guardrailId}`)
    .then((r) => r.data)

// ─── Decision Log (M-012) ──────────────────────────────────────────────────
// Append-only decision history per experiment. UI hides the form for
// users without `decisions:write` (see DecisionLogTab.jsx for the
// permission check using user.permissions[]).
export const getDecisions = (experimentId, params = {}) =>
  api
    .get(`/api/v1/experiments/${experimentId}/decisions`, { params })
    .then((r) => r.data)

export const addDecision = (experimentId, data) =>
  api
    .post(`/api/v1/experiments/${experimentId}/decisions`, data)
    .then((r) => r.data)
