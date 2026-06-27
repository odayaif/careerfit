import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function ClusterPanel() {
  const [clusters, setClusters] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.analyticsClusters()
      .then(res => setClusters(res.clusters || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="loading-spinner">טוען אשכולות...</div>
  if (error) return <div className="error-box">{error}</div>
  if (clusters.length === 0) {
    return (
      <div className="cluster-panel">
        <div style={{ color: 'var(--text-3)', fontSize: 12, textAlign: 'center', padding: 20 }}>
          אין אשכולות זמינים. הרץ clustering תחילה.
        </div>
      </div>
    )
  }

  return (
    <div className="cluster-panel">
      <div className="section-header">🔵 אשכולות קריירה</div>
      {clusters.map((c, i) => (
        <div key={i} className="cluster-card">
          <div className="cluster-card-title">{c.suggested_direction}</div>
          <div className="cluster-meta">
            <span>📦 {(c.job_count || 0).toLocaleString()} משרות</span>
            {c.dominant_categories && (
              <span>🗂 {c.dominant_categories}</span>
            )}
            {c.top_locations && (
              <span>📍 {c.top_locations}</span>
            )}
          </div>
          {c.top_keywords && (
            <div className="cluster-keywords">
              מילות מפתח: {c.top_keywords}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
