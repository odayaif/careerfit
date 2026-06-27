import React from 'react'

// ── Score badge ─────────────────────────────────────────────────────────────
function ScoreBadge({ score }) {
  // score is already 0-100 (normalized by backend); guard against undefined
  const pct = typeof score === 'number' ? score : 0
  const cls = pct >= 70 ? 'high' : pct >= 45 ? 'med' : 'low'
  return <span className={`match-score-badge ${cls}`}>{pct.toFixed(0)}%</span>
}

// ── Location badge ───────────────────────────────────────────────────────────
function LocationBadge({ job }) {
  const loc = job.location || job.location_clean || ''
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
      return loc ? `📍 ${loc}` : null
  }
}

// ── Single job card ──────────────────────────────────────────────────────────
function JobCard({ job }) {
  if (!job || typeof job !== 'object') return null

  // Field name normalization: backend may return _clean suffixed names
  const title         = job.title         || job.title_clean         || '(ללא כותרת)'
  const company       = job.company_name  || job.company_clean       || ''
  const expLevel      = job.experience_level || job.experience_level_clean || ''
  const workType      = job.work_type     || job.work_type_clean     || ''
  const salary        = job.salary_display || ''
  const matchReasons  = Array.isArray(job.match_reasons) ? job.match_reasons : []
  const warnings      = Array.isArray(job.warnings)      ? job.warnings      : []
  const missingSkills = Array.isArray(job.missing_skills) ? job.missing_skills
                      : Array.isArray(job.skill_gaps)    ? job.skill_gaps    : []
  const anomalyFlags  = Array.isArray(job.anomaly_flags) ? job.anomaly_flags : []
  const url           = job.application_url || job.job_posting_url || ''

  return (
    <div className="job-card">
      <div className="job-card-header">
        <div>
          <div className="job-title">{title}</div>
          {company && <div className="job-company">&#x1F3E2; {company}</div>}
        </div>
        <ScoreBadge score={job.match_score} />
      </div>

      <div className="job-meta">
        {(job.job_country || job.location || job.location_clean) && (
          <span className="job-tag">
            <LocationBadge job={job} />
          </span>
        )}
        {job.job_category && (
          <span className="job-tag">&#x1F5C2; {job.job_category}</span>
        )}
        {expLevel && expLevel !== 'לא צוין' && (
          <span className="job-tag">&#x1F3AF; {expLevel}</span>
        )}
        {workType && workType !== 'לא צוין' && (
          <span className="job-tag">{workType}</span>
        )}
        {salary && salary !== 'לא צוין' && (
          <span className="job-tag salary">&#x1F4B0; {salary}</span>
        )}
        {anomalyFlags.length > 0 && (
          <span className="job-tag warning">&#x26A0; {anomalyFlags[0]}</span>
        )}
      </div>

      {matchReasons.length > 0 && (
        <div className="job-reasons">
          <div className="job-reasons-title">סיבות התאמה:</div>
          {matchReasons.map((r, i) => (
            <div key={i} className="job-reason-item">{r}</div>
          ))}
        </div>
      )}

      {warnings.length > 0 && (
        <div style={{ marginTop: 6 }}>
          {warnings.map((w, i) => (
            <div key={i} className="job-warning-item">{w}</div>
          ))}
        </div>
      )}

      {missingSkills.length > 0 && (
        <div className="job-missing-skills">
          כישורים לחיזוק: {missingSkills.join(', ')}
        </div>
      )}

      {url && (
        <a href={url} target="_blank" rel="noopener noreferrer" className="job-apply-btn">
          לפרטים והגשה ←
        </a>
      )}
    </div>
  )
}

// ── Country mix debug bar ────────────────────────────────────────────────────
function CountryMixBar({ meta }) {
  const m = meta?.location_scope_debug?.results_country_mix || {}
  const parts = []
  if (m.Israel > 0)                 parts.push(`🇮🇱 ${m.Israel} ישראל`)
  if (m.Israel_possible_remote > 0) parts.push(`🌐 ${m.Israel_possible_remote} אפשרי`)
  if (m['United States'] > 0)       parts.push(`🇺🇸 ${m['United States']} ארה"ב`)
  if (m.unknown_remote > 0)         parts.push(`🌐 ${m.unknown_remote} לא ודאי`)
  if (m.Other > 0)                  parts.push(`🌍 ${m.Other} אחר`)
  if (!parts.length) return null
  return (
    <div style={{ fontSize: 11, color: 'var(--text-2)', padding: '0 0 6px', opacity: 0.7 }}>
      {parts.join(' · ')}
    </div>
  )
}

// ── Main export ──────────────────────────────────────────────────────────────
export default function JobResults({ jobs, searchMeta }) {
  // Guard: jobs can be undefined, null, or empty
  const safeJobs = Array.isArray(jobs) ? jobs : []

  if (safeJobs.length === 0) {
    return (
      <div className="jobs-empty">
        ספר/י על הרקע שלך בצ׳אט ואמצא משרות מתאימות.
      </div>
    )
  }

  return (
    <div className="jobs-panel">
      <div className="jobs-header">
        נמצאו {safeJobs.length} משרות
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
      <CountryMixBar meta={searchMeta} />
      {safeJobs.map((job, i) => (
        <JobCard key={job?.job_id ?? i} job={job} />
      ))}
    </div>
  )
}
