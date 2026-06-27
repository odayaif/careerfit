import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

function BarChart({ data, maxItems = 8 }) {
  if (!data || data.length === 0) return <div style={{ color: 'var(--text-3)', fontSize: 12 }}>אין נתונים</div>
  const items = data.slice(0, maxItems)
  const maxVal = Math.max(...items.map(d => d.value || d.count || 0), 1)

  return (
    <div className="bar-chart">
      {items.map((d, i) => {
        const val = d.value || d.count || 0
        const pct = (val / maxVal) * 100
        const label = d.label || d.name || d.category || '—'
        return (
          <div key={i} className="bar-item">
            <span className="bar-label" title={label}>{label}</span>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${pct}%` }} />
            </div>
            <span className="bar-count">{val.toLocaleString()}</span>
          </div>
        )
      })}
    </div>
  )
}

function StatCard({ title, value, sub }) {
  return (
    <div className="insight-card">
      <div className="insight-title">{title}</div>
      <div className="insight-value">{value}</div>
      {sub && <div className="insight-sub">{sub}</div>}
    </div>
  )
}

export default function DataDashboard() {
  const [summary, setSummary] = useState(null)
  const [trends, setTrends] = useState(null)
  const [anomalies, setAnomalies] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const [s, t, a] = await Promise.all([
          api.analyticsSummary(),
          api.analyticsTrends(),
          api.analyticsAnomalies(),
        ])
        setSummary(s)
        setTrends(t)
        setAnomalies(a)
      } catch (e) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) return <div className="loading-spinner">טוען נתונים...</div>
  if (error) return <div className="error-box">{error}</div>

  const demoMode = summary?.demo_mode
  if (demoMode) {
    return (
      <div className="dashboard">
        <div className="error-box" style={{ background: '#fffbeb', borderColor: '#fde68a', color: '#92400e' }}>
          {summary.message}
        </div>
      </div>
    )
  }

  return (
    <div className="dashboard">
      {/* KPI Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
        <StatCard title="סך משרות" value={(summary?.total_jobs || 0).toLocaleString()} />
        <StatCard
          title="עבודה מרחוק"
          value={`${summary?.remote_pct || 0}%`}
          sub={`${(summary?.remote_count || 0).toLocaleString()} משרות`}
        />
        <StatCard
          title="ללא שכר"
          value={`${summary?.no_salary_pct || 0}%`}
          sub="משרות ללא מידע שכר"
        />
      </div>

      {/* Categories */}
      <div className="dashboard-section">
        <div className="dashboard-section-title">קטגוריות מובילות</div>
        <BarChart data={trends?.categories} />
      </div>

      {/* Areas */}
      <div className="dashboard-section">
        <div className="dashboard-section-title">אזורים גאוגרפיים</div>
        <BarChart data={trends?.areas} />
      </div>

      {/* Experience */}
      <div className="dashboard-section">
        <div className="dashboard-section-title">רמות ניסיון</div>
        <BarChart data={trends?.experience} />
      </div>

      {/* Work types */}
      <div className="dashboard-section">
        <div className="dashboard-section-title">סוגי עבודה</div>
        <BarChart data={trends?.work_types} />
      </div>

      {/* Quality */}
      <div className="dashboard-section">
        <div className="dashboard-section-title">איכות משרות</div>
        <BarChart data={trends?.quality_distribution} />
      </div>

      {/* Anomalies */}
      {anomalies?.anomalies && (
        <div className="dashboard-section">
          <div className="dashboard-section-title">חריגות מרכזיות</div>
          {Object.entries(anomalies.anomalies).map(([name, val], i) => {
            if (!val || typeof val !== 'object') return null
            return (
              <div key={i} className="stat-row">
                <span>{name}</span>
                <span className="stat-value">
                  {typeof val.count === 'number' ? val.count.toLocaleString() : '—'}
                  {val.pct != null ? ` (${val.pct}%)` : ''}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
