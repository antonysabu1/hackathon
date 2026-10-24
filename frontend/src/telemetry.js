// Turns the raw lap JSON ({ lap_time, frames: [{ t, speed, throttle, brake, steering, gear, dt }] })
// and the backend's /analyze result into what the charts and panels need.
// Distance is integrated the same way the backend does it (speed * dt), so zones line up.

export const ISSUE_LABEL = {
  braking_too_hard_or_too_late: 'Braking too hard or late',
  throttle_too_conservative: 'Throttle too cautious',
  excess_steering_input: 'Too much steering',
  unclear_technique_issue: 'Slow here, cause unclear',
}

export const ISSUE_HELP = {
  braking_too_hard_or_too_late: {
    meaning: 'You were braking harder than the reference at this point, so you were slower.',
    fix: 'Brake a touch earlier and release smoothly, rather than stabbing the pedal late.',
  },
  throttle_too_conservative: {
    meaning: 'The reference was on the throttle more than you at this point.',
    fix: 'Get on the power earlier and roll it in as the steering unwinds.',
  },
  excess_steering_input: {
    meaning: 'You were turning the wheel more than the reference here, which scrubs speed.',
    fix: 'Use a smoother, wider line and avoid big corrections.',
  },
  unclear_technique_issue: {
    meaning: 'You were much slower than the reference here, but pedals and steering do not point to one clear cause.',
    fix: 'Compare the speed trace in this zone and look at where your speed drops away first.',
  },
}

function prep(frames) {
  const n = frames.length
  const d = new Float64Array(n)
  const t = new Float64Array(n)
  const t0 = frames[0].t
  for (let i = 0; i < n; i++) {
    if (i > 0) d[i] = d[i - 1] + (frames[i].speed / 3.6) * (frames[i].dt ?? 0.01)
    t[i] = frames[i].t - t0
  }
  return { d, t, frames }
}

// Linear interpolation of ys over increasing xs, evaluated on a sorted grid.
function interpGrid(xs, ys, grid) {
  const out = new Array(grid.length)
  const n = xs.length
  let j = 0
  for (let k = 0; k < grid.length; k++) {
    const g = grid[k]
    while (j < n - 2 && xs[j + 1] < g) j++
    const x0 = xs[j]
    const x1 = xs[j + 1]
    const f = x1 === x0 ? 0 : Math.min(1, Math.max(0, (g - x0) / (x1 - x0)))
    out[k] = ys[j] + (ys[j + 1] - ys[j]) * f
  }
  return out
}

const r2 = (x, n = 2) => Math.round(x * 10 ** n) / 10 ** n

export function buildTraces(youLap, refLap, points = 1100) {
  if (!youLap.frames?.length || youLap.frames.length < 3) throw new Error('Your lap has too few frames.')
  if (!refLap.frames?.length || refLap.frames.length < 3) throw new Error('The reference lap has too few frames.')
  const u = prep(youLap.frames)
  const r = prep(refLap.frames)
  const L = Math.min(u.d[u.d.length - 1], r.d[r.d.length - 1])
  if (!(L > 50)) throw new Error('These laps cover almost no distance. Is the speed in km/h?')
  const grid = Array.from({ length: points }, (_, i) => (i / (points - 1)) * L)

  const chan = (lap, name) => lap.frames.map((f) => f[name])
  const pack = (p) => ({
    speed: interpGrid(p.d, chan(p, 'speed'), grid).map((v) => r2(v, 1)),
    throttle: interpGrid(p.d, chan(p, 'throttle'), grid).map((v) => r2(v, 3)),
    brake: interpGrid(p.d, chan(p, 'brake'), grid).map((v) => r2(v, 3)),
    steer: interpGrid(p.d, chan(p, 'steering'), grid).map((v) => r2(v, 3)),
  })
  const tu = interpGrid(u.d, u.t, grid)
  const tr = interpGrid(r.d, r.t, grid)

  return {
    d: grid.map((v) => r2(v, 1)),
    you: pack({ d: u.d, frames: u.frames }),
    ref: pack({ d: r.d, frames: r.frames }),
    delta: tu.map((v, i) => r2(v - tr[i], 3)),
    length: L,
  }
}

// Group the backend's per-point issues into zones (a braking zone, a corner exit, ...).
export function buildZones(issues, dMax, gap = 150, pad = 60) {
  const sorted = [...issues].sort((a, b) => a.distance_m - b.distance_m)
  const groups = []
  for (const it of sorted) {
    const g = groups[groups.length - 1]
    if (g && it.distance_m - g[g.length - 1].distance_m <= gap) g.push(it)
    else groups.push([it])
  }
  const zones = groups.map((pts, i) => {
    const worst = pts.reduce((a, b) => (b.speed_delta > a.speed_delta ? b : a))
    const counts = {}
    pts.forEach((p) => (counts[p.issue_type] = (counts[p.issue_type] || 0) + 1))
    const main = Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0]
    return {
      id: i + 1,
      name: `Z${i + 1}`,
      start_d: Math.max(0, pts[0].distance_m - pad),
      end_d: Math.min(dMax, pts[pts.length - 1].distance_m + pad),
      worst,
      points: pts,
      main_issue: worst.issue_type !== 'unclear_technique_issue' ? worst.issue_type : main,
    }
  })
  const ranking = [...zones].sort((a, b) => b.worst.speed_delta - a.worst.speed_delta).map((z) => z.id)
  return { zones, ranking }
}

export function nearestIndex(d, target) {
  let lo = 0
  let hi = d.length - 1
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (d[mid] < target) lo = mid
    else hi = mid
  }
  return Math.abs(d[lo] - target) <= Math.abs(d[hi] - target) ? lo : hi
}

export function fmtTime(s) {
  const m = Math.floor(s / 60)
  const sec = (s - m * 60).toFixed(3).padStart(6, '0')
  return `${m}:${sec}`
}

// ---- extra channels (recorded live from the game) ----
const distCache = new WeakMap()
export function lapDistance(lap) {
  let d = distCache.get(lap)
  if (!d) {
    d = prep(lap.frames).d
    distCache.set(lap, d)
  }
  return d
}

export function hasChannel(lap, key) {
  const f = lap && lap.frames
  return !!f && f.length > 2 && typeof f[0][key] === 'number'
}

// Resamples one frame channel onto the shared distance grid.
export function buildChannel(lap, key, grid) {
  const d = lapDistance(lap)
  return interpGrid(d, lap.frames.map((f) => f[key]), grid).map((v) => r2(v, 3))
}

// ---- corners: find each turn on the lap and how much time you lose in it ----
// A corner is a dip in the reference speed (the car slows, then speeds up again). We measure your lap against
// the reference through that stretch, from where the braking starts to where the speed is back up.
export function findCorners(traces, minDrop = 15) {
  const d = traces.d
  const n = d.length
  if (n < 50) return []
  const smooth = (a, k = 3) => a.map((_, i) => {
    let sum = 0, c = 0
    for (let j = Math.max(0, i - k); j <= Math.min(n - 1, i + k); j++) { sum += a[j]; c++ }
    return sum / c
  })
  const ref = smooth(traces.ref.speed)
  const you = traces.you.speed
  const win = Math.max(8, Math.round((n / (d[n - 1] || 1)) * 120)) // about 120 m either side
  const found = []
  for (let i = 1; i < n - 1; i++) {
    if (!(ref[i] <= ref[i - 1] && ref[i] < ref[i + 1])) continue
    // walk outward while the speed keeps rising, so the stretch ends where the car is back up to speed
    let a = i
    while (a > 0 && ref[a - 1] >= ref[a] - 0.01 && i - a < win * 4) a--
    let b = i
    while (b < n - 1 && ref[b + 1] >= ref[b] - 0.01 && b - i < win * 4) b++
    const drop = Math.min(ref[a], ref[b]) - ref[i]
    if (drop < minDrop) continue
    const prev = found[found.length - 1]
    if (prev && d[i] - d[prev.apex] < 80) {
      if (ref[i] < ref[prev.apex]) { prev.apex = i; prev.a = Math.min(prev.a, a); prev.b = Math.max(prev.b, b) }
      continue
    }
    found.push({ apex: i, a, b })
  }
  return found.map((c, k) => {
    let youMin = Infinity, refMin = Infinity
    for (let j = c.a; j <= c.b; j++) { youMin = Math.min(youMin, you[j]); refMin = Math.min(refMin, traces.ref.speed[j]) }
    const timeLoss = traces.delta[c.b] - traces.delta[c.a]
    return {
      id: k + 1,
      name: `T${k + 1}`,
      apex_d: d[c.apex],
      start_d: d[c.a],
      end_d: d[c.b],
      you_min: youMin,
      ref_min: refMin,
      speed_loss: refMin - youMin,
      time_loss: timeLoss,
    }
  })
}
