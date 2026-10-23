import { useEffect, useRef, useState } from 'react'
import { sendChat } from './api'

export default function Coach({ analysisId, corners }) {
  const snapCorner = corners.find((c) => c.snap)
  const chips = [
    'Where am I losing the most time?',
    snapCorner ? `Why did ${snapCorner.name} snap?` : 'What should I fix first?',
    'Is it my driving or the setup?',
  ]
  const [msgs, setMsgs] = useState([
    { role: 'assistant', text: 'I have read your lap. Ask me why you are slow somewhere, or what to try next lap.', source: 'intro' },
  ])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const end = useRef(null)

  useEffect(() => {
    end.current?.scrollIntoView({ block: 'nearest' })
  }, [msgs, busy])

  async function send(message) {
    const m = message.trim()
    if (!m || busy) return
    const history = msgs.filter((x) => x.source !== 'intro')
    setMsgs((x) => [...x, { role: 'user', text: m }])
    setText('')
    setBusy(true)
    try {
      const res = await sendChat(analysisId, m, history)
      setMsgs((x) => [...x, { role: 'assistant', text: res.text, source: res.source }])
    } catch (e) {
      setMsgs((x) => [...x, { role: 'assistant', text: 'Could not reach the coach: ' + e.message, source: 'error' }])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="panel coach">
      <div className="panel-title">Coach</div>
      <div className="chat">
        {msgs.map((m, i) => (
          <div key={i} className={'bubble ' + m.role}>
            {m.text}
            {m.role === 'assistant' && m.source === 'offline' && <span className="src">offline coach</span>}
            {m.role === 'assistant' && m.source === 'claude' && <span className="src">Claude</span>}
          </div>
        ))}
        {busy && <div className="bubble assistant typing"><i /><i /><i /></div>}
        <div ref={end} />
      </div>
      <div className="chips">
        {chips.map((c) => (
          <button key={c} onClick={() => send(c)} disabled={busy}>
            {c}
          </button>
        ))}
      </div>
      <form
        className="chat-input"
        onSubmit={(e) => {
          e.preventDefault()
          send(text)
        }}
      >
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Ask about a corner, a snap, a setup change"
        />
        <button type="submit" disabled={busy || !text.trim()}>
          Send
        </button>
      </form>
    </div>
  )
}
