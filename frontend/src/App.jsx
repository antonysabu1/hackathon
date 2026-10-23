import { useEffect, useMemo, useState } from 'react'
import TraceChart from './Charts'
import { CornerList, CornerDetail } from './Corners'
import Coach from './Coach'
import { analyzeFiles, getHealth, loadSample } from './api'

function fmtTime(s) {
  const m = Math.floor(s / 60)
  const sec = (s - m * 60).toFixed(3).padStart(6, '0')
  return `${m}:${sec}`
}

function FilePick({ label, hint, file, onFile }) {
  return (
    <label className={'drop' + (file ? ' has' : '')}>
      <input type="file" accept=".csv,.txt" onChange={(e) => onFile(e.target.files[0] || null)} />
      <span className="drop-label">{label}</span>
      <span className="drop-file">{file ? file.name : hint}</span>
    </label>
  )
}

function Landing({ onSample, onAnalyze, busy }) {
  const [lap, setLap] = useState(null)
  const [ref, setRef] = useState(null)
  return (
    <section className="landing">
      <p className="eyebrow">Telemetry, explained</p>
      <h1>
        Know <em>why</em> you are slow,
        <br />
        not just where.
      </h1>
      <p className="sub">
        Upload a lap. Get the corner, the cause and the fix in plain words. Inputs are checked before the car
        setup is blamed.
      </p>

      <div className="drops">
        <FilePick label="Your lap" hint="Choose a telemetry CSV" file={lap} onFile={setLap} />
        <FilePick label="Reference lap (optional)" hint="Defaults to the built in reference" file={ref} onFile={setRef} />
      </div>

      <div className="actions">
        <button className="primary" disabled={!lap || busy} onClick={() => onAnalyze(lap, ref)}>
          {busy ? 'Analysing' : 'Analyse my lap'}
        </button>
        <button className="ghost" disabled={busy} onClick={onSample}>
          Try the sample lap
        </button>
      </div>
      <p className="fine">
        No game installed? The sample is a synthetic lap with deliberate mistakes: an early brake, an abrupt
        release that snaps the rear, and a late throttle.
      </p>
    </section>
  )
}

function Hero({ s }) {
  const slower = s.delta > 0.02
  return (
    <section className="hero">
      <div className="cell">
        <span className="k">Your lap</span>
        <span className="v">{fmtTime(s.you_time)}</span>
      </div>
      <div className="cell">
        <span className="k">Reference</span>
        <span className="v dimv">{fmtTime(s.ref_time)}</span>
      </div>
      <div className="cell">
        <span className="k">Gap</span>
        <span className={'v ' + (slower ? 'loss' : 'gain')}>
          {s.delta >= 0 ? '+' : ''}
          {s.delta.toFixed(3)}
        </span>
      </div>
      <div className="cell wide">
        <span className="k">Realistic gain if you fix the flags</span>
        <span className="v small">
          {s.potential.low.toFixed(2)} to {s.potential.high.toFixed(2)} s
        </span>
        <span className="note">An estimate, shown as a range.</span>
      </div>
      <p className="headline">{s.headline}</p>
    </section>
  )
}

function Readout({ a, i }) {
  if (i === null || i === undefined) {
    return <div className="readout idle">Hover a chart to read values. Click a shaded corner to inspect it.</div>
  }
  const t = a.traces
  const cell = (k, v) => (
    <span>
      <b>{k}</b>
      {v}
    </span>
  )
  return (
    <div className="readout">
      {cell('Dist', `${Math.round(t.d[i])} m`)}
      {cell('Speed', `${Math.round(t.you.speed[i])} / ${Math.round(t.ref.speed[i])} km/h`)}
      {cell('Throttle', `${Math.round(t.you.throttle[i] * 100)}%`)}
      {cell('Brake', `${Math.round(t.you.brake[i] * 100)}%`)}
      {cell('Steer', t.you.steer[i].toFixed(2))}
      {cell('Delta', `${t.delta[i] >= 0 ? '+' : ''}${t.delta[i].toFixed(2)} s`)}
    </div>
  )
}

export default function App() {
  const [health, setHealth] = useState(undefined)
  const [analysis, setAnalysis] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)
  const [hover, setHover] = useState(null)

  useEffect(() => {
    getHealth().then(setHealth)
  }, [])

  async function run(fn) {
    setBusy(true)
    setError(null)
    try {
      const a = await fn()
      setAnalysis(a)
      setSelected(a.ranking[0])
    } catch (e) {
      setError(e.message === 'Failed to fetch' ? 'Cannot reach the backend. Is it running on port 8000?' : e.message)
    } finally {
      setBusy(false)
    }
  }

  const charts = useMemo(() => {
    if (!analysis) return null
    const t = analysis.traces
    return {
      speed: [
        { values: t.ref.speed, color: 'var(--ref)', width: 1.4, dash: '5 4' },
        { values: t.you.speed, color: 'var(--you)', width: 1.9 },
      ],
      pedals: [
        { values: t.you.throttle, color: 'var(--thr)', width: 1.4, area: true, opacity: 0.22 },
        { values: t.you.brake, color: 'var(--brk)', width: 1.4, area: true, opacity: 0.3 },
        { values: t.ref.brake, color: 'var(--ref)', width: 1, dash: '4 4' },
      ],
      steer: [
        { values: t.ref.steer, color: 'var(--ref)', width: 1.2, dash: '5 4' },
        { values: t.you.steer, color: 'var(--you)', width: 1.7 },
      ],
      delta: [{ values: t.delta, color: 'var(--loss)', width: 1.8, area: true, opacity: 0.16 }],
    }
  }, [analysis])

  const selectedCorner = analysis && analysis.corners.find((c) => c.id === selected)
  const common = analysis && {
    d: analysis.traces.d,
    corners: analysis.corners,
    selected,
    onSelect: setSelected,
    hover,
    onHover: setHover,
  }
  const youRef = [
    { label: 'You', color: 'var(--you)' },
    { label: 'Reference', color: 'var(--ref)' },
  ]

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <span className="mark" />
          APEX COACH
        </div>
        <div className="top-right">
          <span className={'pill ' + (health ? 'ok' : 'off')}>
            {health === undefined ? 'Checking' : health ? (health.claude ? 'Claude connected' : 'Offline coach') : 'Backend offline'}
          </span>
          {analysis && (
            <button className="ghost small" onClick={() => setAnalysis(null)}>
              New lap
            </button>
          )}
        </div>
      </header>

      {error && <div className="error">{error}</div>}

      {!analysis && <Landing busy={busy} onSample={() => run(loadSample)} onAnalyze={(l, r) => run(() => analyzeFiles(l, r))} />}

      {analysis && (
        <main className="grid">
          <div className="col-main">
            <Hero s={analysis.summary} />
            {analysis.warnings.length > 0 && <div className="notice">{analysis.warnings.join(' ')}</div>}
            <Readout a={analysis} i={hover} />
            <div className="panel charts">
              <TraceChart {...common} title="Speed (km/h)" series={charts.speed} height={190} decimals={0} legend={youRef} />
              <TraceChart
                {...common}
                title="Throttle and brake"
                series={charts.pedals}
                height={110}
                domain={[0, 1.05]}
                decimals={1}
                areaBase={0}
                legend={[
                  { label: 'Throttle', color: 'var(--thr)' },
                  { label: 'Brake', color: 'var(--brk)' },
                  { label: 'Ref brake', color: 'var(--ref)' },
                ]}
              />
              <TraceChart {...common} title="Steering" series={charts.steer} height={100} decimals={1} />
              <TraceChart {...common} title="Time gap to reference (s)" series={charts.delta} height={110} decimals={1} areaBase={0} />
            </div>
            <CornerList corners={analysis.corners} ranking={analysis.ranking} selected={selected} onSelect={setSelected} />
          </div>

          <aside className="col-side">
            <CornerDetail corner={selectedCorner} />
            <Coach key={analysis.id} analysisId={analysis.id} corners={analysis.corners} />
          </aside>
        </main>
      )}
    </div>
  )
}
