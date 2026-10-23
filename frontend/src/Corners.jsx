export const ISSUE_LABEL = {
  early_brake: 'Early braking',
  late_brake: 'Late braking',
  over_slow: 'Slow apex',
  abrupt_release: 'Abrupt release',
  late_throttle: 'Late throttle',
  abrupt_throttle: 'Sharp throttle',
  under_grip: 'Grip unused',
  snap: 'Snap',
}

const num = (v, d = 0) => (v === null || v === undefined ? null : Number(v).toFixed(d))

export function CornerList({ corners, ranking, selected, onSelect }) {
  const byId = Object.fromEntries(corners.map((c) => [c.id, c]))
  const maxLoss = Math.max(0.05, ...corners.map((c) => c.time_loss))
  return (
    <div className="panel">
      <div className="panel-title">Where the time went</div>
      <div className="corner-list">
        {ranking.map((id, i) => {
          const c = byId[id]
          const loss = c.time_loss
          const main = c.issues[0]
          return (
            <button
              key={id}
              className={'corner-row' + (selected === id ? ' on' : '')}
              onClick={() => onSelect(id)}
            >
              <span className="rank">{i + 1}</span>
              <span className="cname">{c.name}</span>
              <span className="lossbar">
                <i
                  style={{
                    width: `${Math.max(0, Math.min(1, loss / maxLoss)) * 100}%`,
                    background: loss > 0.03 ? 'var(--loss)' : 'var(--gain)',
                  }}
                />
              </span>
              <span className="lossval">{loss >= 0 ? '+' : ''}{loss.toFixed(2)}s</span>
              <span className={'tag' + (main ? (main.type === 'snap' ? ' tag-hot' : '') : ' tag-ok')}>
                {main ? ISSUE_LABEL[main.type] : 'Clean'}
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
  if (you !== null && rv !== null && better) {
    const diff = better === 'high' ? you - rv : rv - you
    tone = diff < -0.001 ? 'bad' : diff > 0.001 ? 'good' : ''
  }
  const f = (v) => (v === null ? 'n/a' : v + unit)
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className={'stat-you ' + tone}>{f(you)}</span>
      <span className="stat-ref">{f(rv)}</span>
    </div>
  )
}

export function CornerDetail({ corner }) {
  if (!corner) return null
  const u = corner.you
  const r = corner.ref
  const before = (x) => (x.brake_start_d === null ? null : Number(num(corner.apex_d - x.brake_start_d)))
  const gripU = u.grip === null ? null : Number(num(u.grip * 100))
  const gripR = r.grip === null ? null : Number(num(r.grip * 100))

  return (
    <div className="panel detail">
      <div className="panel-title">
        {corner.name} <span className="dim">· {corner.time_loss >= 0 ? '+' : ''}{corner.time_loss.toFixed(2)} s</span>
      </div>

      <div className="stat stat-head">
        <span />
        <span>You</span>
        <span>Ref</span>
      </div>
      <Stat label="Brake starts, m before apex" you={before(u)} rv={before(r)} unit="" better="low" />
      <Stat label="Minimum speed" you={num(u.min_speed) === null ? null : Number(num(u.min_speed))} rv={Number(num(r.min_speed))} unit=" km/h" better="high" />
      <Stat label="Brake release length" you={u.release_len === null ? null : Number(num(u.release_len))} rv={r.release_len === null ? null : Number(num(r.release_len))} unit=" m" />
      <Stat label="Throttle on, m after apex" you={u.throttle_on_d === null ? null : Number(num(u.throttle_on_d))} rv={r.throttle_on_d === null ? null : Number(num(r.throttle_on_d))} unit="" better="low" />
      <Stat label="Exit speed" you={Number(num(u.exit_speed))} rv={Number(num(r.exit_speed))} unit=" km/h" better="high" />
      <Stat label="Grip used" you={gripU} rv={gripR} unit="%" better="high" />

      <div className="issues">
        {corner.issues.length === 0 && (
          <div className="issue ok">
            <b>Clean corner.</b> Nothing worth changing here against this reference.
          </div>
        )}
        {corner.issues.map((i, k) => (
          <div key={k} className={'issue ' + (i.type === 'snap' ? 'hot' : '')}>
            <div className="issue-head">{ISSUE_LABEL[i.type]}</div>
            <p>{i.message}</p>
            <p className="try">
              <b>Try:</b> {i.fix}
            </p>
          </div>
        ))}
        {corner.snap && corner.snap.blame === 'setup' && (
          <div className="issue setup">
            <div className="issue-head">Setup experiments (one at a time)</div>
            <ol>
              {corner.snap.options.map((o) => (
                <li key={o}>{o}</li>
              ))}
            </ol>
            <p className="dim">Change one thing, run about 8 clean laps, then compare.</p>
          </div>
        )}
      </div>
    </div>
  )
}
