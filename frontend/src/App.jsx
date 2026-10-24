import { useEffect, useMemo, useState } from 'react'
import TraceChart from './Charts'
import { ZoneList, ZoneDetail, CornerTable } from './Zones'
import { Coach, Leaderboard } from './Insight'
import Chat from './Chat'
import Profile, { bestOtherId } from './Profile'
import SessionForm, { EMPTY_META } from './SessionForm'
import { Conditions, MoreTelemetry, TrackMap } from './LiveCharts'
import { analyzeLap, demoFile, getHealth, getLap, getProfile, saveSession, uploadLap } from './api'
import { buildTraces, buildZones, fmtTime } from './telemetry'

async function readLap(file, label) {
  let json
  try {
    json = JSON.parse(await file.text())
  } catch (e) {
    throw new Error(`${label} is not a valid JSON file.`)
  }
  if (!json || !Array.isArray(json.frames)) {
    throw new Error(`${label} needs a "frames" list. Expected { lap_time, frames: [{ t, speed, throttle, brake, steering, dt }] }.`)
  }
  return json
}

// Reads car, track, setup, fuel and tyre wear out of a lap file when it has them.
// Looks for top level car/track/setup, and for fuel / tyre_wear channels on the frames.
async function detectMeta(file) {
  try {
    const j = JSON.parse(await file.text())
    const m = { ...(j.meta || {}), ...j }
    const found = {}
    if (typeof m.car === 'string') found.car = m.car
    if (typeof m.track === 'string') found.track = m.track
    if (m.setup && typeof m.setup === 'object') found.setup = m.setup
    const f = Array.isArray(j.frames) ? j.frames : []
    if (f.length > 1) {
      const a = f[0]
      const b = f[f.length - 1]
      if (typeof a.fuel === 'number' && typeof b.fuel === 'number') {
        found.fuel = { start: a.fuel.toFixed(1), end: b.fuel.toFixed(1) }
        found.laps_run = '1'
      }
      if (typeof a.tyre_wear === 'number' && typeof b.tyre_wear === 'number') {
        found.tyre = { wear_start: a.tyre_wear.toFixed(1), wear_end: b.tyre_wear.toFixed(1) }
        found.laps_run = '1'
      }
    }
    return found
  } catch (e) {
    return {}
  }
}

function FilePick({ label, hint, file, onFile }) {
  return (
    <label className={'drop' + (file ? ' has' : '')}>
      <input type="file" accept=".json,application/json" onChange={(e) => onFile(e.target.files[0] || null)} />
      <span className="drop-label">{label}</span>
      <span className="drop-file">{file ? file.name : hint}</span>
    </label>
  )
}

function Landing({ onDemo, onAnalyze, busy, stage, driver, setDriver, meta, setMeta }) {
  const [lap, setLap] = useState(null)
  const [ref, setRef] = useState(null)
  const [auto, setAuto] = useState([])
  async function pickLap(file) {
    setLap(file)
    setAuto([])
    if (!file) return
    const d = await detectMeta(file)
    const names = []
    const next = { ...meta, setup: { ...meta.setup }, tyre: { ...meta.tyre }, fuel: { ...meta.fuel } }
    if (d.car) (next.car = d.car), names.push('car')
    if (d.track) (next.track = d.track), names.push('track')
    if (d.setup) (next.setup = { ...next.setup, ...d.setup }), names.push('setup')
    if (d.fuel) (next.fuel = { ...next.fuel, ...d.fuel }), names.push('fuel')
    if (d.tyre) (next.tyre = { ...next.tyre, ...d.tyre }), names.push('tyre wear')
    if (d.laps_run) next.tyre.laps_run = d.laps_run
    if (names.length) {
      setMeta(next)
      setAuto(names)
    }
  }
  return (
    <section className="landing">
      <p className="eyebrow">Telemetry, explained</p>
      <h1>
        Know <em>why</em> you are slow,
        <br />
        not just where.
      </h1>
      <p className="sub">
        Upload a lap and a reference lap. We find where you lost speed and the AI coach explains it in plain words.
      </p>

      <div className="drops">
        <FilePick label="Your lap" hint="Choose a lap JSON file" file={lap} onFile={pickLap} />
        <FilePick label="Reference lap" hint="A faster lap on the same track" file={ref} onFile={setRef} />
      </div>
      {auto.length > 0 && <p className="notice">Read from your lap file: {auto.join(', ')}. You can still edit them below.</p>}
      <label className="field">
        <span className="drop-label">Driver name</span>
        <input value={driver} onChange={(e) => setDriver(e.target.value)} maxLength={40} />
      </label>
      <details className="more" open>
        <summary>Car, setup, tyres and fuel</summary>
        <SessionForm meta={meta} onChange={setMeta} />
      </details>

      <div className="actions">
        <button className="primary" disabled={!lap || !ref || busy} onClick={() => onAnalyze(lap, ref)}>
          {busy ? 'Working' : 'Analyse my lap'}
        </button>
        <button className="ghost" disabled={busy} onClick={() => onDemo()}>
          Try the demo laps
        </button>
      </div>
      {busy && <p className="stage">{stage}</p>}
      <p className="fine">
        Both files must be full laps of the same track. The demo laps are synthetic, with deliberate mistakes such as an early
        brake, a late throttle and a snap in the fast right hander.
      </p>
    </section>
  )
}

function Hero({ you, refLap, analysis, zones }) {
  const gap = you.lap_time - refLap.lap_time
  const n = analysis.total_issues_found
  const w = analysis.worst_issue
  const headline =
    n === 0
      ? 'No point was more than 15 km/h slower than the reference.'
      : `${n} flagged ${n === 1 ? 'point' : 'points'} in ${zones.length} ${zones.length === 1 ? 'zone' : 'zones'}. ` +
        `Biggest gap: ${w.speed_delta.toFixed(0)} km/h slower at ${Math.round(w.distance_m)} m.`
  return (
    <section className="hero">
      <div className="cell">
        <span className="k">Your lap</span>
        <span className="v">{fmtTime(you.lap_time)}</span>
      </div>
      <div className="cell">
        <span className="k">Reference</span>
        <span className="v dimv">{fmtTime(refLap.lap_time)}</span>
      </div>
      <div className="cell">
        <span className="k">Gap</span>
        <span className={'v ' + (gap > 0.02 ? 'loss' : 'gain')}>
          {gap >= 0 ? '+' : ''}
          {gap.toFixed(3)}
        </span>
      </div>
      <div className="cell wide">
        <span className="k">Problem points</span>
        <span className="v small">{n}</span>
        <span className="note">Points 15+ km/h slower than the reference.</span>
      </div>
      <p className="headline">{headline}</p>
    </section>
  )
}

function Readout({ t, i }) {
  if (i === null || i === undefined) {
    return <div className="readout idle">Hover a chart to read values. Click a shaded zone to inspect it.</div>
  }
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
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(false)
  const [stage, setStage] = useState('')
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)
  const [pickedCorner, setPickedCorner] = useState(null)
  const [hover, setHover] = useState(null)
  const [runs, setRuns] = useState(0)
  const [tab, setTab] = useState('profile')
  const [toast, setToast] = useState(null)
  const [driver, setDriverState] = useState(() => {
    try {
      return localStorage.getItem('apex-driver') || 'Siva'
    } catch (e) {
      return 'Siva'
    }
  })
  const [meta, setMeta] = useState(EMPTY_META)
  const setDriver = (name) => {
    setDriverState(name)
    try {
      localStorage.setItem('apex-driver', name)
    } catch (e) {
      /* storage blocked, fine */
    }
  }
  const who = driver.trim() || 'Driver'

  useEffect(() => {
    getHealth().then(setHealth)
  }, [])

  // Watches for laps recorded from the game and announces each new one.
  useEffect(() => {
    let live = true
    let known = null
    const poll = async () => {
      try {
        const p = await getProfile(who)
        if (!live) return
        const all = p.tracks.flatMap((t) => t.cars.flatMap((c) => c.sessions))
        const ids = new Set(all.map((s) => s.lap_id))
        if (known === null) {
          known = ids // first look: existing laps are not "new"
          return
        }
        const fresh = all.filter((s) => !known.has(s.lap_id) && s.valid !== false).sort((a, b) => b.lap_id - a.lap_id)[0]
        const added = all.some((s) => !known.has(s.lap_id))
        known = ids
        if (added) setRuns((n) => n + 1)
        if (fresh) {
          setToast({ lap: fresh, refId: bestOtherId(p.tracks, fresh) })
        }
      } catch (e) {
        /* backend not up yet, try again next tick */
      }
    }
    poll()
    const timer = setInterval(poll, 3000)
    return () => {
      live = false
      clearInterval(timer)
    }
  }, [who])

  async function run(lapFile, refFile) {
    setBusy(true)
    setError(null)
    try {
      setStage('Reading your laps')
      const [youJson, refJson] = await Promise.all([readLap(lapFile, 'Your lap'), readLap(refFile, 'The reference lap')])
      const traces = buildTraces(youJson, refJson) // fails early on bad files

      setStage('Uploading your lap')
      const track = meta.track.trim() || 'Unknown'
      const car = meta.car.trim() || 'Unknown'
      const up = await uploadLap(lapFile, { driver: who, track, car })
      setStage('Uploading the reference lap')
      const upRef = await uploadLap(refFile, { driver: 'Reference', track, car: meta.refCar.trim() || car })
      setStage('Saving to your profile')
      try {
        await saveSession({
          lap_id: up.lap_id,
          driver: who,
          track,
          car,
          setup: meta.setup,
          tyre: meta.tyre,
          fuel: meta.fuel,
          notes: meta.notes,
        })
      } catch (e) {
        setError('The lap was analysed but could not be saved to your profile: ' + e.message)
      }
      setStage('Analysing and asking the coach')
      const analysis = await analyzeLap(up.lap_id, upRef.lap_id)
      setStage('Loading the coaching')
      const lap = await getLap(up.lap_id)

      const { zones, ranking } = buildZones(analysis.issues || [], traces.length)
      setData({ you: up, ref: upRef, youJson, refJson, track, car, analysis, traces, zones, ranking, insights: lap.insights || [] })
      setSelected(ranking[0] ?? null)
      setPickedCorner(null)
      setRuns((n) => n + 1)
    } catch (e) {
      setError(
        e.message === 'Failed to fetch'
          ? 'Cannot reach the backend on port 8000. Start it first. Its server also needs ANTHROPIC_API_KEY in a .env file, or it will not start.'
          : e.message,
      )
    } finally {
      setBusy(false)
      setStage('')
    }
  }

  // Compare two laps that are already saved (for example recorded live), no files needed.
  async function compareSaved(youId, refId) {
    setTab('analyse')
    setData(null)
    setBusy(true)
    setError(null)
    try {
      setStage('Loading both laps')
      const [you, ref] = await Promise.all([getLap(youId), getLap(refId)])
      const traces = buildTraces(you.telemetry, ref.telemetry)
      setStage('Analysing and asking the coach')
      const analysis = await analyzeLap(youId, refId)
      const fresh = await getLap(youId)
      const { zones, ranking } = buildZones(analysis.issues || [], traces.length)
      setData({
        youJson: you.telemetry,
        refJson: ref.telemetry,
        you: { lap_id: you.id, lap_time: you.lap_time },
        ref: { lap_id: ref.id, lap_time: ref.lap_time },
        track: you.track,
        car: you.car,
        analysis,
        traces,
        zones,
        ranking,
        insights: fresh.insights || [],
      })
      setSelected(ranking[0] ?? null)
      setPickedCorner(null)
      setRuns((n) => n + 1)
    } catch (e) {
      setError(e.message === 'Failed to fetch' ? 'Cannot reach the backend on port 8000.' : e.message)
    } finally {
      setBusy(false)
      setStage('')
    }
  }

  async function runDemo() {
    try {
      const [a, b] = await Promise.all([demoFile('your_lap.json'), demoFile('reference_lap.json')])
      await run(a, b)
    } catch (e) {
      setError(e.message)
    }
  }

  const charts = useMemo(() => {
    if (!data) return null
    const t = data.traces
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
  }, [data])

  const zone = data && data.zones.find((z) => z.id === selected)
  const common = data && {
    d: data.traces.d,
    corners: data.zones,
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
            {health === undefined ? 'Checking' : health ? 'Backend online' : 'Backend offline'}
          </span>
          <nav className="tabs">
            <button className={tab === 'profile' ? 'on' : ''} onClick={() => setTab('profile')}>
              My laps
            </button>
            <button className={tab === 'analyse' ? 'on' : ''} onClick={() => setTab('analyse')}>
              Analysis
            </button>
          </nav>
          {data && tab === 'analyse' && (
            <button className="ghost small" onClick={() => setData(null)}>
              New lap
            </button>
          )}
        </div>
      </header>

      {toast && (
        <div className="toast">
          <div>
            <b>New lap recorded</b> · {fmtTime(toast.lap.lap_time)} · {toast.lap.track} · {toast.lap.car}
          </div>
          <div className="toast-actions">
            {toast.refId ? (
              <button
                className="primary small"
                disabled={busy}
                onClick={() => {
                  const t = toast
                  setToast(null)
                  compareSaved(t.lap.lap_id, t.refId)
                }}
              >
                Analyse vs my best
              </button>
            ) : (
              <span className="dim">Drive one more lap to compare.</span>
            )}
            <button className="ghost small" onClick={() => setToast(null)}>
              Dismiss
            </button>
          </div>
        </div>
      )}

      {error && <div className="error">{error}</div>}

      {tab === 'profile' && <Profile driver={who} onDriver={setDriver} refreshKey={runs} onCompare={compareSaved} busy={busy} />}

      {tab === 'analyse' && !data && (
        <Landing
          busy={busy}
          stage={stage}
          onDemo={runDemo}
          onAnalyze={run}
          driver={driver}
          setDriver={setDriver}
          meta={meta}
          setMeta={setMeta}
        />
      )}

      {tab === 'analyse' && data && (
        <main className="grid">
          <div className="col-main">
            <p className="session-line">
              {who} · {data.track} · {data.car} · saved to your profile
            </p>
            <Conditions lap={data.youJson} />
            <Hero you={data.you} refLap={data.ref} analysis={data.analysis} zones={data.zones} />
            <Readout t={data.traces} i={hover} />
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
            <MoreTelemetry you={data.youJson} refLap={data.refJson} grid={data.traces.d} common={common} />
            <CornerTable traces={data.traces} selected={pickedCorner && pickedCorner.id} onSelect={(c) => setPickedCorner(pickedCorner && pickedCorner.id === c.id ? null : c)} />
            <ZoneList zones={data.zones} ranking={data.ranking} selected={selected} onSelect={(id) => { setPickedCorner(null); setSelected(id) }} />
          </div>

          <aside className="col-side">
            <TrackMap you={data.youJson} zone={pickedCorner || zone} />
            <ZoneDetail zone={zone} traces={data.traces} insights={data.insights} />
            <Coach insights={data.insights} worst={data.analysis.worst_issue} />
            <Chat driver={who} track={data.track} car={data.car} lapId={data.you.lap_id} />
            <Leaderboard refreshKey={runs} />
          </aside>
        </main>
      )}
    </div>
  )
}
