import { useEffect, useState } from 'react'
import { getLeaderboard } from './api'
import { fmtTime } from './telemetry'

export function Coach({ insights, worst }) {
  return (
    <div className="panel">
      <div className="panel-title">Coach</div>
      {insights.length === 0 && (
        <p className="dim">No coaching text came back for this lap. The backend only asks the coach when it finds a problem point.</p>
      )}
      {insights.map((x, i) => (
        <div key={i} className="bubble assistant">
          {x.insight}
          <span className="src">Claude · {x.corner.replace('distance_', 'at ')}</span>
        </div>
      ))}
      {worst && (
        <p className="dim fine-print">
          The coach comments on your single biggest gap, {worst.speed_delta.toFixed(0)} km/h slower at {Math.round(worst.distance_m)} m.
        </p>
      )}
    </div>
  )
}

export function Leaderboard({ refreshKey }) {
  const [rows, setRows] = useState(null)
  useEffect(() => {
    let live = true
    getLeaderboard(8)
      .then((r) => live && setRows(Array.isArray(r) ? r : []))
      .catch(() => live && setRows([]))
    return () => {
      live = false
    }
  }, [refreshKey])

  if (!rows || rows.length === 0) return null
  return (
    <div className="panel">
      <div className="panel-title">Leaderboard · lap times only</div>
      <div className="lb">
        {rows.map((r, i) => (
          <div key={r.lap_id} className="lb-row">
            <span className="rank">{i + 1}</span>
            <span>{r.driver}</span>
            <span className="lb-time">{fmtTime(r.lap_time)}</span>
          </div>
        ))}
      </div>
      <p className="dim fine-print">Only lap times are shown. Other drivers' telemetry stays private.</p>
    </div>
  )
}
