import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function InsightsPanel() {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.analyticsSummary()
      .then(setSummary)
      .catch(() => setSummary(null))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div style={{ padding: 12, color: 'var(--text-3)', fontSize: 12 }}>טוען...</div>
  if (!summary || summary.demo_mode) return null

  const cats = summary.top_categories || []
  const areas = summary.top_areas || []

  return (
    <div className="insights-panel">
      <div className="section-header">📊 תובנות מהירות</div>

      <div className="insight-card">
        <div className="insight-title">קטגוריה מבוקשת ביותר</div>
        <div className="insight-value" style={{ fontSize: 16 }}>
          {cats[0]?.name || '—'}
        </div>
        <div className="insight-sub">
          {cats[0] ? `${(cats[0].count || 0).toLocaleString()} משרות` : ''}
        </div>
      </div>

      <div className="insight-card">
        <div className="insight-title">אזור עם הכי הרבה משרות</div>
        <div className="insight-value" style={{ fontSize: 16 }}>
          {areas[0]?.name || '—'}
        </div>
        <div className="insight-sub">
          {areas[0] ? `${(areas[0].count || 0).toLocaleString()} משרות` : ''}
        </div>
      </div>

      <div className="insight-card">
        <div className="insight-title">שיעור עבודה מרחוק</div>
        <div className="insight-value">{summary.remote_pct || 0}%</div>
        <div className="insight-sub">מתוך {(summary.total_jobs || 0).toLocaleString()} משרות</div>
      </div>

      <div className="insight-card">
        <div className="insight-title">משרות ללא שכר</div>
        <div className="insight-value" style={{ color: 'var(--warning)' }}>
          {summary.no_salary_pct || 0}%
        </div>
        <div className="insight-sub">לא צוין שכר</div>
      </div>
    </div>
  )
}
