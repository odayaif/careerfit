import React, { useState, useEffect, Component } from 'react'
import Layout from './components/Layout.jsx'
import Chat from './components/Chat.jsx'
import UserProfile from './components/UserProfile.jsx'
import JobResults from './components/JobResults.jsx'
import DataDashboard from './components/DataDashboard.jsx'
import InsightsPanel from './components/InsightsPanel.jsx'
import ClusterPanel from './components/ClusterPanel.jsx'
import { api } from './api.js'

const EMPTY_PROFILE = {
  education: { degree: '', field: '', status: '' },
  experience: { years: null, previous_roles: [], seniority: '' },
  skills: [],
  career_interests: [],
  salary_expectation: { min: null, preferred: null, flexible: true },
  location_preference: { primary: '', fallbacks: [], remote_allowed: true },
  work_style: { preferred_environment: '' },
  constraints: { avoid: [], must_have: [] },
  conversation: { language: 'Hebrew' },
}

// Center panel tabs
const CENTER_TABS = [
  { id: 'chat', label: "💬 צ'אט" },
  { id: 'jobs', label: '📋 משרות' },
  { id: 'dashboard', label: '📊 דשבורד' },
]

// Right panel tabs
const RIGHT_TABS = [
  { id: 'insights', label: '💡 תובנות' },
  { id: 'clusters', label: '🔵 אשכולות' },
]

// ── Top-level error boundary: prevents blank white screen on any render crash ─
class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }
  componentDidCatch(error, info) {
    console.error('[CareerFit] Render error:', error, info)
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          justifyContent: 'center', height: '100vh', gap: 16,
          fontFamily: 'sans-serif', direction: 'rtl', color: '#444'
        }}>
          <div style={{ fontSize: 48 }}>💼</div>
          <h2>CareerFit</h2>
          <p>נתקלתי בבעיה קטנה. רענן/י את הדף כדי להמשיך.</p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{ padding: '8px 20px', borderRadius: 8, cursor: 'pointer' }}
          >
            נסה שוב
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

export default function App() {
  const [profile, setProfile]         = useState(EMPTY_PROFILE)
  const [completeness, setCompleteness] = useState(0)
  const [jobs, setJobs]               = useState([])
  const [searchMeta, setSearchMeta]   = useState({})
  const [centerTab, setCenterTab]     = useState('chat')
  const [rightTab, setRightTab]       = useState('insights')
  const [healthStatus, setHealthStatus] = useState({ status: 'loading' })

  // Check health on mount
  useEffect(() => {
    api.health()
      .then(h => setHealthStatus(h))
      .catch(() => setHealthStatus({ status: 'error' }))
  }, [])

  function handleProfileUpdate(newProfile, newCompleteness) {
    setProfile(newProfile)
    setCompleteness(newCompleteness || 0)
  }

  function handleJobsUpdate(newJobs, meta, clearFirst = false) {
    if (clearFirst) {
      setJobs([])
      setSearchMeta({})
    }
    setJobs(newJobs)
    setSearchMeta(meta || {})
    // Only switch to jobs tab if we actually have results
    if (newJobs && newJobs.length > 0) {
      setCenterTab('jobs')
    }
  }

  // Header
  const statusDot  = healthStatus.status === 'ok' ? '' : 'warn'
  const statusText = healthStatus.status === 'ok'
    ? `שרת פעיל · ${(healthStatus.db_stats?.total_jobs || 0).toLocaleString()} משרות`
    : healthStatus.status === 'no_zip'  ? 'שרת פעיל · דאטה לא נמצא'
    : healthStatus.status === 'no_data' ? 'שרת פעיל · דאטה לא עובד'
    : healthStatus.status === 'error'   ? 'שרת לא נגיש'
    : 'מתחבר...'

  const header = (
    <>
      <div className="header-brand">
        <div>
          <div className="header-logo">💼 CareerFit</div>
          <div className="header-subtitle">סוכן חכם למציאת עבודה והכוונת קריירה</div>
        </div>
      </div>
      <div className="header-status">
        <div className={`status-dot ${statusDot}`} />
        <span>{statusText}</span>
      </div>
    </>
  )

  // Sidebar (profile)
  const sidebar = <UserProfile profile={profile} completeness={completeness} />

  // Center panel
  const center = (
    <>
      <div className="tab-bar">
        {CENTER_TABS.map(t => (
          <button
            key={t.id}
            className={`tab-btn ${centerTab === t.id ? 'active' : ''}`}
            onClick={() => setCenterTab(t.id)}
          >
            {t.label}
            {t.id === 'jobs' && jobs.length > 0 && (
              <span className="badge badge-blue" style={{ marginRight: 6, fontSize: 10 }}>
                {jobs.length}
              </span>
            )}
          </button>
        ))}
      </div>
      <div className="scrollable" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {centerTab === 'chat' && (
          <Chat
            profile={profile}
            onProfileUpdate={handleProfileUpdate}
            onJobsUpdate={handleJobsUpdate}
          />
        )}
        {centerTab === 'jobs' && (
          <JobResults jobs={jobs} searchMeta={searchMeta} />
        )}
        {centerTab === 'dashboard' && <DataDashboard />}
      </div>
    </>
  )

  // Right panel
  const rightPanel = (
    <>
      <div className="tab-bar" style={{ borderBottom: '1px solid var(--border)' }}>
        {RIGHT_TABS.map(t => (
          <button
            key={t.id}
            className={`tab-btn ${rightTab === t.id ? 'active' : ''}`}
            onClick={() => setRightTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {rightTab === 'insights'  && <InsightsPanel />}
      {rightTab === 'clusters'  && <ClusterPanel />}
    </>
  )

  return (
    <ErrorBoundary>
      <Layout
        header={header}
        sidebar={sidebar}
        center={center}
        rightPanel={rightPanel}
      />
    </ErrorBoundary>
  )
}
