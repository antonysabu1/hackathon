import { useEffect, useRef, useState } from 'react'
import { askCoach } from './api'

const IDEAS = [
  'Where am I losing the most time?',
  'What should I change in my setup?',
  'Is my car snapping because of the setup or my inputs?',
  'How fast are my tyres wearing?',
]

export default function Chat({ driver, track, car, lapId, title = 'Ask the coach' }) {
  const [msgs, setMsgs] = useState([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const end = useRef(null)

  useEffect(() => {
    end.current && end.current.scrollIntoView({ block: 'nearest' })
  }, [msgs, busy])

  async function send(q) {
    const question = (q ?? text).trim()
    if (!question || busy) return
    const history = msgs.map((m) => ({ role: m.role, text: m.text }))
    setMsgs((m) => [...m, { role: 'user', text: question }])
    setText('')
    setBusy(true)
    try {
      const res = await askCoach({ driver, question, track, car, lap_id: lapId ?? null, history })
      setMsgs((m) => [...m, { role: 'assistant', text: res.answer }])
    } catch (e) {
      setMsgs((m) => [
        ...m,
        { role: 'assistant', text: e.message === 'Failed to fetch' ? 'Cannot reach the backend.' : e.message, bad: true },
      ])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="panel chat">
      <div className="panel-title">
        {title}
        {(track || car) && <span className="scope">{[track, car].filter(Boolean).join(' · ')}</span>}
      </div>
      <div className="chat-log">
        {msgs.length === 0 && (
          <div className="ideas">
            {IDEAS.map((q) => (
              <button key={q} className="idea" onClick={() => send(q)}>
                {q}
              </button>
            ))}
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={'bubble ' + m.role + (m.bad ? ' bad' : '')}>
            {m.text}
          </div>
        ))}
        {busy && <div className="bubble assistant dim">Thinking</div>}
        <div ref={end} />
      </div>
      <form
        className="chat-in"
        onSubmit={(e) => {
          e.preventDefault()
          send()
        }}
      >
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask about your laps, setup, tyres, fuel" />
        <button className="primary" disabled={busy || !text.trim()}>
          Ask
        </button>
      </form>
    </div>
  )
}
