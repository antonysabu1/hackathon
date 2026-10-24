import { useMemo, useState } from 'react'
import TraceChart from './Charts'
import { buildChannel, hasChannel, lapDistance } from './telemetry'

const WHEEL_COLORS = ['#ffb21f', '#6e9bff', '#3ddc84', '#ff7a6e']
const wheels = (p) => ['fl', 'fr', 'rl', 'rr'].map((w) => `${p}_${w}`)
const WHEEL_LEGEND = ['FL', 'FR', 'RL', 'RR'].map((label, i) => ({ label, color: WHEEL_COLORS[i] }))

// Each group is one chart. One channel: you against the reference. Four wheels: your lap only.
const GROUPS = [
  { id: 'rpm', title: 'Engine RPM', keys: ['rpm'], decimals: 0 },
  { id: 'glat', title: 'Lateral G (cornering load)', keys: ['g_lat'], decimals: 1 },
  { id: 'glong', title: 'Longitudinal G (braking and accel)', keys: ['g_long'], decimals: 1 },
  { id: 'slip', title: 'Wheel slip (grip being used)', keys: wheels('slip'), decimals: 1 },
  { id: 'ttemp', title: 'Tyre core temperature (C)', keys: wheels('tyre_temp'), decimals: 0 },
  { id: 'press', title: 'Tyre pressure (psi)', keys: wheels('pressure'), decimals: 1 },
  { id: 'wear', title: 'Tyre wear (%)', keys: wheels('wear'), decimals: 1 },
  { id: 'btemp', title: 'Brake temperature (C)', keys: wheels('brake_temp'), decimals: 0 },
  { id: 'susp', title: 'Suspension travel', keys: wheels('susp'), decimals: 3 },
  { id: 'fuel', title: 'Fuel (L)', keys: ['fuel'], decimals: 1 },
]

export function Conditions({ lap }) {
  const bits = []
  if (lap.car) bits.push(['Car', lap.car])
  if (lap.tyre_compound) bits.push(['Tyre', lap.tyre_compound])
  if (typeof lap.air_temp === 'number') bits.push(['Air', `${lap.air_temp.toFixed(0)} C`])
  if (typeof lap.road_temp === 'number') bits.push(['Road', `${lap.road_temp.toFixed(0)} C`])
  if (typeof lap.brake_bias === 'number') bits.push(['Brake bias', `${lap.brake_bias.toFixed(1)}%`])
  if (typeof lap.tyre_pressure_avg === 'number') bits.push(['Pressure', `${lap.tyre_pressure_avg} psi`])
  if (typeof lap.damage === 'number') bits.push(['Damage', lap.damage > 0.5 ? 'yes' : 'none'])
  if (bits.length === 0) return null
  return (
    <div className="chips cond">
      {bits.map(([k, v]) => (
        <span key={k} className="chip">
          {k} <b>{v}</b>
        </span>
      ))}
    </div>
  )
}

export function MoreTelemetry({ you, refLap, grid, common }) {
  const groups = useMemo(() => GROUPS.filter((g) => g.keys.every((k) => hasChannel(you, k))), [you])
  const [open, setOpen] = useState(() => new Set(['rpm', 'glat', 'slip']))
  const toggle = (id) =>
    setOpen((s) => {
      const n = new Set(s)
      n.has(id) ? n.delete(id) : n.add(id)
      return n
    })
  if (groups.length === 0) return null

  return (
    <div className="panel">
      <div className="panel-title">More telemetry · recorded from the game</div>
      <div className="chips picker">
        {groups.map((g) => (
          <button key={g.id} className={'chip btn' + (open.has(g.id) ? ' on' : '')} onClick={() => toggle(g.id)}>
            {g.title.split(' (')[0]}
          </button>
        ))}
      </div>
      <div className="charts">
        {groups
          .filter((g) => open.has(g.id))
          .map((g) => {
            const single = g.keys.length === 1
            const series = g.keys.map((k, i) =>
              single
                ? { values: buildChannel(you, k, grid), color: 'var(--you)', width: 1.7 }
                : { values: buildChannel(you, k, grid), color: WHEEL_COLORS[i], width: 1.5 },
            )
            if (single && hasChannel(refLap, g.keys[0])) {
              series.unshift({ values: buildChannel(refLap, g.keys[0], grid), color: 'var(--ref)', width: 1.3, dash: '5 4' })
            }
            return (
              <TraceChart
                key={g.id}
                {...common}
                title={g.title}
                series={series}
                height={110}
                decimals={g.decimals}
                legend={single ? [{ label: 'You', color: 'var(--you)' }, { label: 'Reference', color: 'var(--ref)' }] : WHEEL_LEGEND}
              />
            )
          })}
      </div>
    </div>
  )
}

// The racing line drawn from the game's car coordinates, brighter where you were faster.
export function TrackMap({ you, zone }) {
  const pts = useMemo(() => {
    if (!hasChannel(you, 'x') || !hasChannel(you, 'z')) return null
    const f = you.frames
    const d = lapDistance(you)
    const step = Math.max(1, Math.floor(f.length / 700))
    const out = []
    for (let i = 0; i < f.length; i += step) out.push({ x: f[i].x, y: f[i].z, v: f[i].speed, d: d[i] })
    const xs = out.map((p) => p.x)
    const ys = out.map((p) => p.y)
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys)
    if (!(maxX - minX > 5 || maxY - minY > 5)) return null
    const size = Math.max(maxX - minX, maxY - minY)
    const vmax = Math.max(...out.map((p) => p.v))
    return { out, minX, minY, size, vmax }
  }, [you])
  if (!pts) return null
  const S = 300
  const pad = 14
  const px = (x) => pad + ((x - pts.minX) / pts.size) * (S - 2 * pad)
  const py = (y) => pad + ((y - pts.minY) / pts.size) * (S - 2 * pad)
  return (
    <div className="panel">
      <div className="panel-title">Track map · your line</div>
      <svg viewBox={`0 0 ${S} ${S}`} className="trackmap" role="img" aria-label="Your racing line coloured by speed">
        {pts.out.slice(1).map((p, i) => {
          const a = pts.out[i]
          const inZone = zone && p.d >= zone.start_d && p.d <= zone.end_d
          return (
            <line
              key={i}
              x1={px(a.x)} y1={py(a.y)} x2={px(p.x)} y2={py(p.y)}
              stroke={inZone ? 'var(--loss)' : `hsl(38 100% ${22 + 45 * (p.v / pts.vmax)}%)`}
              strokeWidth={inZone ? 4 : 2.4}
              strokeLinecap="round"
            />
          )
        })}
      </svg>
      <p className="dim fine-print">Brighter is faster.{zone ? ` Red marks ${zone.name}, your selected zone.` : ''}</p>
    </div>
  )
}
