const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function apiCall(path, method = 'GET', body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }
  if (body) opts.body = JSON.stringify(body)
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, opts)
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || `HTTP ${res.status}`)
    }
    return await res.json()
  } catch (e) {
    if (e.message.includes('Failed to fetch') || e.message.includes('NetworkError')) {
      throw new Error('לא ניתן להתחבר לשרת. ודאו שה-Backend פועל בכתובת ' + API_BASE_URL)
    }
    throw e
  }
}

export const api = {
  health: () => apiCall('/health'),
  chat: (message, profile) => apiCall('/chat', 'POST', { message, profile }),
  searchJobs: (profile, limit = 10) => apiCall('/jobs/search', 'POST', { profile, limit }),
  resetProfile: () => apiCall('/profile/reset', 'POST'),
  analyticsSummary: () => apiCall('/analytics/summary'),
  analyticsTrends: () => apiCall('/analytics/trends'),
  analyticsAnomalies: () => apiCall('/analytics/anomalies'),
  analyticsClusters: () => apiCall('/analytics/clusters'),
  processData: () => apiCall('/data/process', 'POST'),
  clusterData: () => apiCall('/data/cluster', 'POST'),
  inspectData: () => apiCall('/data/inspect', 'POST'),
}
