// Thin wrapper over the real TrustTrace backend. Every call here hits
// /api/*, which vite.config.js proxies to the FastAPI server -- there is
// no mocked data path. If the backend is down, callers see a real error,
// not a silently-substituted fake response.

const BASE = '/api'

class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === 'string' ? detail : JSON.stringify(detail))
    this.status = status
    this.detail = detail
  }
}

async function request(path, options = {}) {
  const response = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = body.detail ?? body
    } catch {
      // response had no JSON body; keep statusText
    }
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) return null
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('text/csv')) return response.text()
  return response.json()
}

export const api = {
  health: () => request('/health'),

  listProjects: () => request('/projects'),
  getProject: (id) => request(`/projects/${id}`),
  createProject: (data) => request('/projects', { method: 'POST', body: JSON.stringify(data) }),
  createIntegration: (projectId, data) =>
    request(`/projects/${projectId}/integrations`, { method: 'POST', body: JSON.stringify(data) }),
  validateIntegration: (integrationId) =>
    request(`/integrations/${integrationId}/validate`, { method: 'POST' }),

  listEvaluationPacks: () => request('/evaluation-packs'),
  createEvaluationPack: (data) => request('/evaluation-packs', { method: 'POST', body: JSON.stringify(data) }),

  listDatasets: (projectId) => request(`/projects/${projectId}/datasets`),
  getDataset: (id) => request(`/datasets/${id}`),
  createDataset: (projectId, data) =>
    request(`/projects/${projectId}/datasets`, { method: 'POST', body: JSON.stringify(data) }),
  listDatasetVersions: (datasetId) => request(`/datasets/${datasetId}/versions`),
  createDatasetVersion: (datasetId) => request(`/datasets/${datasetId}/versions`, { method: 'POST' }),

  listTestCases: (datasetId, filters = {}) => {
    const params = new URLSearchParams(
      Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== '' && v != null))
    )
    const qs = params.toString()
    return request(`/datasets/${datasetId}/test-cases${qs ? `?${qs}` : ''}`)
  },
  getTestCase: (id) => request(`/test-cases/${id}`),
  createTestCase: (datasetId, data) =>
    request(`/datasets/${datasetId}/test-cases`, { method: 'POST', body: JSON.stringify(data) }),
  updateTestCase: (id, data) => request(`/test-cases/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  archiveTestCase: (id) => request(`/test-cases/${id}`, { method: 'DELETE' }),
  importTestCases: (datasetId, testCases, allowDuplicates = false) =>
    request(`/datasets/${datasetId}/test-cases/import`, {
      method: 'POST',
      body: JSON.stringify({ test_cases: testCases, allow_duplicates: allowDuplicates }),
    }),
  exportTestCasesUrl: (datasetId, format) => `${BASE}/datasets/${datasetId}/test-cases/export?format=${format}`,

  listRuns: (projectId) => request(`/runs${projectId ? `?project_id=${projectId}` : ''}`),
  getRun: (id) => request(`/runs/${id}`),
  createRun: (data) => request('/runs', { method: 'POST', body: JSON.stringify(data) }),
  reportUrl: (runId, format) => `${BASE}/runs/${runId}/report?format=${format}`,

  compareRuns: (baselineRunId, candidateRunId) =>
    request('/regression/compare', {
      method: 'POST',
      body: JSON.stringify({ baseline_run_id: baselineRunId, candidate_run_id: candidateRunId }),
    }),
}

export { ApiError }
