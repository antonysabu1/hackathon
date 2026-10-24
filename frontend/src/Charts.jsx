import { useMemo } from 'react'

// A small hand-built SVG chart. No chart library, so there is nothing extra to install or break.
const W = 1000
const PAD = { l: 46, r: 12, t: 10, b: 8 }

function linePath(xs, ys, fx, fy) {
  let s = ''
  for (let i = 0; i < xs.length; i++) {
    s += (i ? 'L' : 'M') + fx(xs[i]).toFixed(1) + ' ' + fy(ys[i]).toFixed(1)
  }
  return s
}

/**
 * series: [{ values, color, width, dash, area, opacity }]
 * corners: list of { id, name, start_d, end_d }
 */
export default function TraceChart({
  title,
  d,
  series,
  corners,
  selected,
  onSelect,
  hover,
  onHover,
  height = 150,
  domain,
  decimals = 0,
  areaBase,
  legend,
}) {
  const H = height
  const dMax = d[d.length - 1]
  const fx = (v) => PAD.l + (v / dMax) * (W - PAD.l - PAD.r)

  const [lo, hi] = useMemo(() => {
    if (domain) return domain
    let a = Infinity
    let b = -Infinity
    for (const s of series) {
      for (const v of s.values) {
        if (v < a) a = v
        if (v > b) b = v
      }
    }
    const pad = (b - a) * 0.08 || 1
    return [a - pad, b + pad]
  }, [series, domain])

  const fy = (v) => PAD.t + (1 - (v - lo) / (hi - lo)) * (H - PAD.t - PAD.b)
  const base = fy(areaBase !== undefined ? areaBase : lo)

  const paths = useMemo(
    () =>
      series.map((s) => {
        const line = linePath(d, s.values, fx, fy)
        const area = s.area
          ? `${line}L${fx(d[d.length - 1]).toFixed(1)} ${base.toFixed(1)}L${fx(d[0]).toFixed(1)} ${base.toFixed(1)}Z`
          : null
        return { line, area }
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [series, d, lo, hi, height],
  )

  const ticks = [0, 1, 2, 3].map((i) => lo + ((hi - lo) * i) / 3)

  function move(e) {
    const r = e.currentTarget.getBoundingClientRect()
    const px = ((e.clientX - r.left) / r.width) * W
    const frac = (px - PAD.l) / (W - PAD.l - PAD.r)
    if (frac < 0 || frac > 1) return onHover(null)
    onHover(Math.round(frac * (d.length - 1)))
  }

  return (
    <div className="chart">
      <div className="chart-head">
        <span className="chart-title">{title}</span>
        {legend && (
          <span className="chart-legend">
            {legend.map((l) => (
              <span key={l.label}>
                <i style={{ background: l.color }} />
                {l.label}
              </span>
            ))}
          </span>
        )}
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="chart-svg"
        onMouseMove={move}
        onMouseLeave={() => onHover(null)}
      >
        {corners.map((c) => (
          <g key={c.id} onClick={() => onSelect(c.id)} style={{ cursor: 'pointer' }}>
            <rect
              x={fx(c.start_d)}
              y={PAD.t}
              width={Math.max(fx(c.end_d) - fx(c.start_d), 1)}
              height={H - PAD.t - PAD.b}
              className={selected === c.id ? 'band band-on' : 'band'}
            />
            <text x={fx(c.start_d) + 4} y={PAD.t + 11} className="band-label">
              {c.name}
            </text>
          </g>
        ))}

        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={PAD.l} x2={W - PAD.r} y1={fy(t)} y2={fy(t)} className="gridline" />
            <text x={PAD.l - 6} y={fy(t) + 3} className="tick" textAnchor="end">
              {t.toFixed(decimals)}
            </text>
          </g>
        ))}

        {paths.map((p, i) => (
          <g key={i} pointerEvents="none">
            {p.area && <path d={p.area} fill={series[i].color} opacity={series[i].opacity ?? 0.18} />}
            <path
              d={p.line}
              fill="none"
              stroke={series[i].color}
              strokeWidth={series[i].width ?? 1.6}
              strokeDasharray={series[i].dash}
              strokeLinejoin="round"
            />
          </g>
        ))}

        {hover !== null && hover !== undefined && (
          <line x1={fx(d[hover])} x2={fx(d[hover])} y1={PAD.t} y2={H - PAD.b} className="cursor" />
        )}
      </svg>
    </div>
  )
}
