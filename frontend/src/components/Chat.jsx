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

const API_ERROR_MSG = 'נתקלתי בבעיה רגעית, אבל אפשר להמשיך. נסי לנסח שוב או לבחור כיוון קרוב.'

export default function Chat({ profile, onProfileUpdate, onJobsUpdate }) {
  const [messages, setMessages] = useState([WELCOME_MSG])
  const [input, setInput]       = useState('')
  const [loading, setLoading]   = useState(false)
  const bottomRef = useRef(null)
  const inputRef  = useRef(null)

  // Auto-scroll to bottom whenever messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Re-focus input whenever loading finishes (after bot reply rendered)
  useEffect(() => {
    if (!loading) {
      const t = setTimeout(() => inputRef.current?.focus(), 50)
      return () => clearTimeout(t)
    }
  }, [loading])

  async function sendMessage(text) {
    const msg = (text || input).trim()
    if (!msg || loading) return
    setInput('')

    setMessages(prev => [...prev, { role: 'user', text: msg }])
    setLoading(true)

    try {
      const res = await api.chat(msg, profile)

      console.log('[CareerFit] Intent:', res?.intent)
      console.log('[CareerFit] Profile updated:', res?.profile_updated, '| Changed:', res?.changed_fields)
      console.log('[CareerFit] should_clear_jobs:', res?.should_clear_jobs)
      console.log('[CareerFit] Jobs returned:', res?.jobs?.length ?? 0)

      const replyText = res?.reply || res?.message || API_ERROR_MSG

      setMessages(prev => [...prev, { role: 'agent', text: replyText }])

      if (res?.profile) onProfileUpdate(res.profile, res.profile_completeness ?? 0)

      if (res?.should_clear_jobs) {
        onJobsUpdate(res.jobs || [], res.search_metadata || {}, true)
      } else if (Array.isArray(res?.jobs) && res.jobs.length > 0) {
        onJobsUpdate(res.jobs, res.search_metadata || {}, false)
      }
    } catch (e) {
      console.error('[CareerFit] API error:', e)
      setMessages(prev => [...prev, { role: 'system', text: API_ERROR_MSG }])
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
        {messages.map((m, i) => {
          const safeText = m?.text ?? ''
          return (
            <div key={i} className={`chat-message ${m?.role ?? 'agent'}`}>
              {m?.role === 'agent' && (
                <div className="msg-sender">CareerFit</div>
              )}
              {m?.role === 'user' && (
                <div className="msg-sender" style={{ textAlign: 'left' }}>אתה/את</div>
              )}
              {safeText}
            </div>
          )
        })}
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
