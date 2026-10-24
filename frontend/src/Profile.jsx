import { useEffect, useState } from 'react'
import Chat from './Chat'
import { getProfile } from './api'
import { fmtTime } from './telemetry'

const SETUP_LABEL = {
  brake_bias: 'Brake bias',
  front_wing: 'Front wing',
  rear_wing: 'Rear wing',
  arb_front: 'Front ARB',
  arb_rear: 'Rear ARB',
  diff_preload: 'Diff preload',
  pressure_front: 'Front psi',
  pressure_rear: 'Rear psi',
}

const nice = (k) => k.replace(/_/g, ' ').toLowerCase().replace(/^./, (c) => c.toUpperCase())

// Best other lap on the same track and car, so any lap can be compared against something.
export function bestOtherId(tracks, s) {
  const t = tracks.find((x) => x.track === s.track)
  const c = t && t.cars.find((x) => x.car === s.car)
  if (!c) return null
  const others = c.sessions.filter((x) => x.lap_time && x.valid !== false && x.lap_id !== s.lap_id)
  if (others.length === 0) return null
  return others.reduce((a, b) => (b.lap_time < a.lap_time ? b : a)).lap_id
}

function chips(obj, labels = SETUP_LABEL) {
  return Object.entries(obj || {}).filter(([, v]) => v !== '' && v !== null && v !== undefined)
    .map(([k, v]) => ({ k: labels[k] || nice(k), v }))
}

function SessionRow({ s, best, bestId, onCompare, busy }) {
  const setup = chips(s.setup)
  const d = s.derived || {}
  const gap = best && s.lap_time ? s.lap_time - best : null
  return (
    <div className="srow">
      <div className="srow-time">
        <b>{s.lap_time ? fmtTime(s.lap_time) : '-'}</b>
        {gap !== null && <span className={gap < 0.001 ? 'gain' : 'loss'}>{gap < 0.001 ? 'best' : `+${gap.toFixed(3)}`}</span>}
      </div>
      <div className="srow-body">
        {s.valid === false && <p className="invalid-why">{s.invalid_reason || 'Probably invalidated in the game'}</p>}
        <div className="chips">
          {setup.length === 0 && <span className="dim">No setup recorded</span>}
          {setup.map((c) => (
            <span key={c.k} className="chip">
              {c.k} <b>{c.v}</b>
            </span>
          ))}
        </div>
        <div className="chips">
          {s.tyre?.compound && (
            <span className="chip">
              Tyre <b>{s.tyre.compound}</b>
            </span>
          )}
          {d.wear_per_lap !== undefined && (
            <span className="chip">
              Wear <b>{d.wear_per_lap}% / lap</b>
            </span>
          )}
          {d.fuel_per_lap !== undefined && (
            <span className="chip">
              Fuel <b>{d.fuel_per_lap} L / lap</b>
            </span>
          )}
          {s.notes && <span className="chip note">{s.notes}</span>}
        </div>
      </div>
      <div className="srow-side">
        <span className="srow-date dim">{(s.created_at || '').slice(0, 16)}</span>
        {s.valid === false && <span className="badge-bad">Invalid</span>}
        {bestId && s.valid !== false && (
          <button className="ghost small" disabled={busy} onClick={() => onCompare(s.lap_id, bestId)}>
            Analyse vs my {s.lap_time && s.lap_time <= best ? 'next best' : 'best'}
          </button>
        )}
      </div>
    </div>
  )
}

export default function Profile({ driver, onDriver, refreshKey, onCompare, busy }) {
  const [name, setName] = useState(driver)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [scope, setScope] = useState({ track: null, car: null })
  const [showInvalid, setShowInvalid] = useState(false)

  useEffect(() => {
    let live = true
    setError(null)
    getProfile(driver)
      .then((p) => live && setData(p))
      .catch((e) => live && setError(e.message === 'Failed to fetch' ? 'Cannot reach the backend on port 8000.' : e.message))
    return () => {
      live = false
    }
  }, [driver, refreshKey])

  return (
    <main className="profile">
      <div className="profile-head">
        <div>
          <p className="eyebrow">Driver profile</p>
          <h2>{driver}</h2>
          <p className="dim">
            {data ? `${data.total_sessions} saved ${data.total_sessions === 1 ? 'lap' : 'laps'} across ${data.tracks.length} ${data.tracks.length === 1 ? 'track' : 'tracks'}` : ' '}
          </p>
        </div>
        <form
          className="who"
          onSubmit={(e) => {
            e.preventDefault()
            if (name.trim()) onDriver(name.trim())
          }}
        >
          <label className="toggle">
            <input type="checkbox" checked={showInvalid} onChange={(e) => setShowInvalid(e.target.checked)} /> Show invalid laps
          </label>
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={40} />
          <button className="ghost small">Switch driver</button>
        </form>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="profile-grid">
        <div className="tracks">
          {data && data.tracks.length === 0 && (
            <div className="panel">
              <p className="dim">
                Nothing saved yet for {driver}. Drive in Assetto Corsa with the recorder running and each lap lands here on its own, grouped by track and car.
              </p>
            </div>
          )}
          {data &&
            data.tracks.map((t) => (
              <section key={t.track} className="panel track">
                <div className="track-head">
                  <h3>{t.track}</h3>
                  <button
                    className={'ghost small' + (scope.track === t.track && !scope.car ? ' on' : '')}
                    onClick={() => setScope({ track: t.track, car: null })}
                  >
                    Ask about this track
                  </button>
                </div>
                {t.cars.map((c) => (
                  <div key={c.car} className="car">
                    <div className="car-head">
                      <span className="car-name">{c.car}</span>
                      <span className="dim">
                        best <b className="best">{c.best ? fmtTime(c.best) : '-'}</b> · {c.sessions.filter((x) => x.valid !== false).length}{' '}
                        valid {c.sessions.filter((x) => x.valid !== false).length === 1 ? 'lap' : 'laps'}
                      </span>
                      <button
                        className={'ghost small' + (scope.car === c.car && scope.track === t.track ? ' on' : '')}
                        onClick={() => setScope({ track: t.track, car: c.car })}
                      >
                        Ask about this car
                      </button>
                    </div>
                    {c.sessions.filter((s) => showInvalid || s.valid !== false).map((s) => (
                      <SessionRow key={s.id} s={s} best={c.best} bestId={bestOtherId(data.tracks, s)} onCompare={onCompare} busy={busy} />
                    ))}
                  </div>
                ))}
              </section>
            ))}
        </div>
        <aside className="profile-chat">
          <Chat key={`${scope.track}|${scope.car}`} driver={driver} track={scope.track} car={scope.car} title="Ask the coach" />
        </aside>
      </div>
    </main>
  )
}
