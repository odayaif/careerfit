import React, { useState, useRef, useEffect } from 'react'
import { api } from '../api.js'

const QUICK_BUTTONS = [
  { label: 'חפש לי משרות', message: 'חפש לי משרות' },
  { label: 'הרחב אזור', message: 'הרחב אזור חיפוש' },
  { label: 'מגמות', message: 'הצג מגמות שוק' },
  { label: 'אשכולות', message: 'הצג אשכולות משרות' },
  { label: 'פערי כישורים', message: 'אילו כישורים חסרים לי?' },
  { label: 'אפס פרופיל', message: 'אפס פרופיל' },
]

const WELCOME_MSG = {
  role: 'agent',
  text: 'שלום! אני CareerFit — סוכן חכם למציאת עבודה.\n\nמה למדת ובאיזה תחום?',
}

export default function Chat({ profile, onProfileUpdate, onJobsUpdate }) {
  const [messages, setMessages] = useState([WELCOME_MSG])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function sendMessage(text) {
    const msg = text || input.trim()
    if (!msg || loading) return
    setInput('')

    setMessages(prev => [...prev, { role: 'user', text: msg }])
    setLoading(true)

    try {
      const res = await api.chat(msg, profile)

      // Debug logs
      console.log('[CareerFit] Intent:', res.intent)
      console.log('[CareerFit] Profile updated:', res.profile_updated, '| Changed:', res.changed_fields)
      console.log('[CareerFit] should_clear_jobs:', res.should_clear_jobs)
      console.log('[CareerFit] Jobs returned:', res.jobs?.length ?? 0)
      console.log('[CareerFit] Profile:', res.profile)

      setMessages(prev => [...prev, { role: 'agent', text: res.reply }])
      if (res.profile) onProfileUpdate(res.profile, res.profile_completeness)

      // Clear stale jobs when career direction changed
      if (res.should_clear_jobs) {
        onJobsUpdate(res.jobs || [], res.search_metadata || {}, true)
      } else if (res.jobs && res.jobs.length > 0) {
        onJobsUpdate(res.jobs, res.search_metadata || {}, false)
      }
    } catch (e) {
      setMessages(prev => [...prev, { role: 'system', text: e.message }])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="chat-container">
      <div className="chat-messages">
        {messages.map((m, i) => (
          <div key={i} className={`chat-message ${m.role}`}>
            {m.role === 'agent' && (
              <div className="msg-sender">🤖 CareerFit</div>
            )}
            {m.role === 'user' && (
              <div className="msg-sender" style={{ textAlign: 'left' }}>אתה/את</div>
            )}
            {m.text}
          </div>
        ))}
        {loading && (
          <div className="typing-indicator">
            <div className="typing-dot" />
            <div className="typing-dot" />
            <div className="typing-dot" />
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="quick-buttons">
        {QUICK_BUTTONS.map((b, i) => (
          <button
            key={i}
            className="quick-btn"
            onClick={() => sendMessage(b.message)}
            disabled={loading}
          >
            {b.label}
          </button>
        ))}
      </div>

      <div className="chat-input-area">
        <textarea
          ref={inputRef}
          className="chat-input"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="כתוב/י כאן בעברית או אנגלית..."
          rows={1}
          disabled={loading}
        />
        <button
          className="chat-send-btn"
          onClick={() => sendMessage()}
          disabled={loading || !input.trim()}
        >
          שלח/י
        </button>
      </div>
    </div>
  )
}
