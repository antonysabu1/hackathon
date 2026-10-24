import { useMemo } from 'react'
import { ISSUE_HELP, ISSUE_LABEL, findCorners, nearestIndex } from './telemetry'

export function ZoneList({ zones, ranking, selected, onSelect }) {
  const byId = Object.fromEntries(zones.map((z) => [z.id, z]))
  const maxLoss = Math.max(40, ...zones.map((z) => z.worst.speed_delta))
  return (
    <div className="panel">
      <div className="panel-title">Where you were slowest</div>
      {zones.length === 0 && <p className="dim">No point was more than 15 km/h slower than the reference. Nice lap.</p>}
      <div className="corner-list">
        {ranking.map((id, i) => {
          const z = byId[id]
          return (
            <button key={id} className={'corner-row' + (selected === id ? ' on' : '')} onClick={() => onSelect(id)}>
              <span className="rank">{i + 1}</span>
              <span className="cname">{z.name}</span>
              <span className="range">
                {Math.round(z.start_d)} to {Math.round(z.end_d)} m
              </span>
              <span className="lossbar">
                <i style={{ width: `${Math.min(1, z.worst.speed_delta / maxLoss) * 100}%`, background: 'var(--loss)' }} />
              </span>
              <span className="lossval">-{z.worst.speed_delta.toFixed(0)} km/h</span>
              <span className={'tag' + (z.main_issue === 'unclear_technique_issue' ? '' : ' tag-hot')}>
                {ISSUE_LABEL[z.main_issue]}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

function Stat({ label, you, rv, unit, better }) {
  let tone = ''
  if (better) {
    const diff = better === 'high' ? you - rv : rv - you
    tone = diff < -2 ? 'bad' : diff > 2 ? 'good' : ''
  }
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className={'stat-you ' + tone}>
        {you}
        {unit}
      </span>
      <span className="stat-ref">
        {rv}
        {unit}
      </span>
    </div>
  )
}

export function ZoneDetail({ zone, traces, insights }) {
  if (!zone) return null
  const w = zone.worst
  const i = nearestIndex(traces.d, w.distance_m)
  const pct = (v) => Math.round(v * 100)
  const help = ISSUE_HELP[zone.main_issue]
  const insight = insights.find((x) => x.corner === `distance_${w.distance_m.toFixed(1)}m`)

  return (
    <div className="panel detail">
      <div className="panel-title">
        {zone.name} <span className="dim">· worst at {Math.round(w.distance_m)} m</span>
      </div>

      <div className="stat stat-head">
        <span>At that point</span>
        <span>You</span>
        <span>Ref</span>
      </div>
      <Stat label="Speed" you={Math.round(w.your_speed)} rv={Math.round(w.ref_speed)} unit=" km/h" better="high" />
      <Stat label="Throttle" you={pct(traces.you.throttle[i])} rv={pct(traces.ref.throttle[i])} unit="%" better="high" />
      <Stat label="Brake" you={pct(traces.you.brake[i])} rv={pct(traces.ref.brake[i])} unit="%" />
      <Stat label="Steering" you={traces.you.steer[i].toFixed(2)} rv={traces.ref.steer[i].toFixed(2)} unit="" />

      <div className="issues">
        <div className="issue">
          <div className="issue-head">{ISSUE_LABEL[zone.main_issue]}</div>
          <p>{help.meaning}</p>
          <p className="try">
            <b>Try:</b> {help.fix}
          </p>
        </div>
        {insight && (
          <div className="issue setup">
            <div className="issue-head">Coach on this spot</div>
            <p>{insight.insight}</p>
          </div>
        )}
        <p className="dim fine-print">
          {zone.points.length} flagged {zone.points.length === 1 ? 'point' : 'points'} in this zone, the worst is {w.speed_delta.toFixed(0)} km/h
          slower than the reference.
        </p>
      </div>
    </div>
  )
}

// Every turn on the lap, with the time you lose or gain in it against the reference. Slow ones are marked.
export function CornerTable({ traces, selected, onSelect }) {
  const corners = useMemo(() => findCorners(traces), [traces])
  if (corners.length === 0) return null
  const SLOW = 0.05 // seconds lost in one turn before we call it slow
  const maxLoss = Math.max(0.2, ...corners.map((c) => Math.abs(c.time_loss)))
  const ranked = [...corners].sort((a, b) => b.time_loss - a.time_loss)
  const slow = corners.filter((c) => c.time_loss >= SLOW).length
  return (
    <div className="panel">
      <div className="panel-title">Turn by turn</div>
      <p className="dim fine-print">
        {slow === 0
          ? 'No turn lost more than 0.05 s against the reference.'
          : `You are slow in ${slow} of ${corners.length} turns. Worst first. Tap a turn to see it on the map.`}
      </p>
      <div className="corner-list">
        {ranked.map((c) => {
          const lost = c.time_loss >= SLOW
          return (
            <button key={c.id} className={'corner-row' + (selected === c.id ? ' on' : '')} onClick={() => onSelect(c)}>
              <span className="cname">{c.name}</span>
              <span className="range">{Math.round(c.apex_d)} m</span>
              <span className="lossbar">
                <i
                  style={{
                    width: `${Math.min(1, Math.abs(c.time_loss) / maxLoss) * 100}%`,
                    background: c.time_loss >= 0 ? 'var(--loss)' : 'var(--gain, #4ade80)',
                  }}
                />
              </span>
              <span className="lossval">
                {c.time_loss >= 0 ? '-' : '+'}
                {Math.abs(c.time_loss).toFixed(2)} s
              </span>
              <span className="range">
                {Math.round(c.you_min)} vs {Math.round(c.ref_min)} km/h
              </span>
              <span className={'tag' + (lost ? ' tag-hot' : '')}>{lost ? 'Slow' : c.time_loss < -SLOW ? 'Faster' : 'Fine'}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
