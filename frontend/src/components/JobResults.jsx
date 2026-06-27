import React from 'react'

function ScoreBadge({ score }) {
  const cls = score >= 70 ? 'high' : score >= 45 ? 'med' : 'low'
  return <span className={`match-score-badge ${cls}`}>{score.toFixed(0)}%</span>
}

function LocationBadge({ job }) {
  const loc = job.location || ''
  switch (job.job_country) {
    case 'Israel':
      return `🇮🇱 ${loc}`
    case 'Israel_possible_remote':
      return `🌐 ייתכן רלוונטי לישראל`
    case 'United States':
      return `🇺🇸 ${loc}`
    case 'unknown_remote':
      return `🌐 מיקום לא ודאי`
    case 'global_or_foreign':
      return `🌐 מרחוק — לא ישראל`
    default:
      return `📍 ${loc}`
  }
}

function JobCard({ job }) {
  const url = job.application_url || job.job_posting_url
  return (
    <div className="job-card">
      <div className="job-card-header">
        <div>
          <div className="job-title">{job.title}</div>
          <div className="job-company">&#x1F3E2; {job.company_name}</div>
        </div>
        <ScoreBadge score={job.match_score} />
      </div>

      <div className="job-meta">
        {job.location && (
          <span className="job-tag">
            <LocationBadge job={job} />
          </span>
        )}
        {job.job_category && <span className="job-tag">&#x1F5C2; {job.job_category}</span>}
        {job.experience_level && job.experience_level !== 'לא צוין' && (
          <span className="job-tag">&#x1F3AF; {job.experience_level}</span>
        )}
        {job.work_type && job.work_type !== 'לא צוין' && (
          <span className="job-tag">{job.work_type}</span>
        )}
        {job.salary_display && job.salary_display !== 'לא צוין' && (
          <span className="job-tag salary">&#x1F4B0; {job.salary_display}</span>
        )}
        {(job.anomaly_flags || []).length > 0 && (
          <span className="job-tag warning">&#x26A0; {job.anomaly_flags[0]}</span>
        )}
      </div>

      {(job.match_reasons || []).length > 0 && (
        <div className="job-reasons">
          <div className="job-reasons-title">סיבות התאמה:</div>
          {job.match_reasons.map((r, i) => (
            <div key={i} className="job-reason-item">{r}</div>
          ))}
        </div>
      )}

      {(job.warnings || []).length > 0 && (
        <div style={{ marginTop: 6 }}>
          {job.warnings.map((w, i) => (
            <div key={i} className="job-warning-item">{w}</div>
          ))}
        </div>
      )}

      {(job.missing_skills || []).length > 0 && (
        <div className="job-missing-skills">
          כישורים לחיזוק: {job.missing_skills.join(', ')}
        </div>
      )}

      {url && (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="job-apply-btn"
        >
          לפרטים והגשה ←
        </a>
      )}
    </div>
  )
}

export default function JobResults({ jobs, searchMeta }) {
  if (!jobs || jobs.length === 0) {
    return (
      <div className="jobs-empty">
        ספר/י על הרקע שלך בצ'אט ואמצא משרות מתאימות.
      </div>
    )
  }

  return (
    <div className="jobs-panel">
      <div className="jobs-header">
        נמצאו {jobs.length} משרות
        {searchMeta?.expanded && (
          <span className="badge badge-yellow" style={{ marginRight: 8 }}>
            הורחב ל{searchMeta.used_location}
          </span>
        )}
      </div>
      {searchMeta?.reason && (
        <div style={{ fontSize: 12, color: 'var(--text-2)', padding: '0 0 4px' }}>
          {searchMeta.reason}
        </div>
      )}
      {searchMeta?.location_scope_debug && (
        <div style={{ fontSize: 11, color: 'var(--text-2)', padding: '0 0 6px', opacity: 0.7 }}>
          {(() => {
            const m = searchMeta.location_scope_debug.results_country_mix || {}
            const parts = []
            if (m.Israel > 0)                 parts.push(`🇮🇱 ${m.Israel} ישראל`)
            if (m.Israel_possible_remote > 0) parts.push(`🌐 ${m.Israel_possible_remote} אפשרי לישראל`)
            if (m['United States'] > 0)       parts.push(`🇺🇸 ${m['United States']} ארה"ב`)
            if (m.unknown_remote > 0)         parts.push(`🌐 ${m.unknown_remote} לא ודאי`)
            if (m.Other > 0)                  parts.push(`🌍 ${m.Other} אחר`)
            return parts.join(' · ')
          })()}
        </div>
      )}
      {jobs.map((job, i) => (
        <JobCard key={job.job_id || i} job={job} />
      ))}
    </div>
  )
}
