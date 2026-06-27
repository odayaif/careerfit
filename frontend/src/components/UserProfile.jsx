import React from 'react'

function Field({ label, value }) {
  if (!value || value === '' || (Array.isArray(value) && value.length === 0)) return null
  const display = Array.isArray(value) ? value.join(', ') : String(value)
  return (
    <div className="profile-field">
      <span className="profile-field-label">{label}</span>
      <span className="profile-field-value">{display}</span>
    </div>
  )
}

const SIGNAL_LABELS = [
  { key: 'hobbies',           label: 'תחביבים' },
  { key: 'interests',         label: 'תחומי עניין' },
  { key: 'personality_traits',label: 'תכונות' },
  { key: 'work_preferences',  label: 'העדפות עבודה' },
  { key: 'career_values',     label: 'ערכים בקריירה' },
  { key: 'free_notes',        label: 'הערות' },
]

function SoftSignalsSection({ signals }) {
  if (!signals) return null
  const rows = SIGNAL_LABELS.filter(({ key }) => (signals[key] || []).length > 0)
  if (rows.length === 0) return null
  return (
    <div className="profile-section">
      <div className="profile-section-title">מאפיינים אישיים</div>
      {rows.map(({ key, label }) => (
        <Field key={key} label={label} value={signals[key]} />
      ))}
    </div>
  )
}

export default function UserProfile({ profile, completeness }) {
  if (!profile) return null

  const edu = profile.education || {}
  const exp = profile.experience || {}
  const sal = profile.salary_expectation || {}
  const loc = profile.location_preference || {}
  const ws = profile.work_style || {}
  const con = profile.constraints || {}

  const isEmpty = (completeness || 0) < 5

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="section-header">👤 הפרופיל שלך</div>

      <div>
        <div className="completeness-label">
          <span>שלמות פרופיל</span>
          <span>{completeness || 0}%</span>
        </div>
        <div className="completeness-bar-wrap">
          <div className="completeness-bar" style={{ width: `${completeness || 0}%` }} />
        </div>
      </div>

      {isEmpty && (
        <div className="profile-empty-hint">
          כדי להתחיל, כתוב/י בצ'אט מה למדת, אילו כישורים יש לך ואיפה תרצה/י לעבוד.
        </div>
      )}

      {!isEmpty && (
        <>
          <div className="profile-section">
            <div className="profile-section-title">השכלה</div>
            <Field label="תואר" value={edu.degree} />
            <Field label="תחום" value={edu.field} />
            <Field label="סטטוס" value={edu.status} />
          </div>

          <div className="profile-section">
            <div className="profile-section-title">ניסיון</div>
            <Field label="שנים" value={exp.years != null ? `${exp.years} שנים` : null} />
            <Field label="רמה" value={exp.seniority} />
            <Field label="תפקידים" value={exp.previous_roles} />
          </div>

          {(profile.skills || []).length > 0 && (
            <div className="profile-section">
              <div className="profile-section-title">כישורים</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, paddingTop: 4 }}>
                {profile.skills.map((s, i) => (
                  <span key={i} className="badge badge-blue">{s}</span>
                ))}
              </div>
            </div>
          )}

          {(profile.career_interests || []).length > 0 && (
            <div className="profile-section">
              <div className="profile-section-title">תחומי עניין</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, paddingTop: 4 }}>
                {profile.career_interests.map((i, idx) => (
                  <span key={idx} className="badge badge-green">{i}</span>
                ))}
              </div>
            </div>
          )}

          <div className="profile-section">
            <div className="profile-section-title">ציפיות שכר</div>
            <Field
              label="מועדף"
              value={sal.preferred ? `₪${sal.preferred.toLocaleString()}` : null}
            />
            <Field
              label="מינימום"
              value={sal.min ? `₪${sal.min.toLocaleString()}` : null}
            />
            <Field label="גמישות" value={sal.flexible ? 'גמיש' : 'קפדני'} />
          </div>

          <div className="profile-section">
            <div className="profile-section-title">מיקום</div>
            <Field label="ראשי" value={loc.primary} />
            <Field label="חלופות" value={loc.fallbacks} />
            <Field label="מרחוק" value={loc.remote_allowed ? 'מוכן/ה' : 'לא'} />
          </div>

          <div className="profile-section">
            <div className="profile-section-title">סגנון עבודה</div>
            <Field label="סביבה" value={ws.preferred_environment} />
          </div>

          {(con.avoid || []).length > 0 && (
            <div className="profile-section">
              <div className="profile-section-title">אילוצים</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, paddingTop: 4 }}>
                {con.avoid.map((a, i) => (
                  <span key={i} className="badge badge-red">לא: {a}</span>
                ))}
              </div>
            </div>
          )}

          <SoftSignalsSection signals={profile.profile_signals} />
        </>
      )}
    </div>
  )
}
