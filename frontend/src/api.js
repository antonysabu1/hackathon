// All calls to the backend live here. The backend is the FastAPI app in the repo root (main.py).
// In dev, Vite forwards /api/... to http://127.0.0.1:8000/... (see vite.config.js).

const BASE = '/api'

async function handle(res) {
  let body = null
  try {
    body = await res.json()
  } catch (e) {
    /* not JSON */
  }
  if (!res.ok) {
    const detail = body && body.detail ? (typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)) : null
    throw new Error(detail || `Request failed (${res.status})`)
  }
  // The backend reports some failures with HTTP 200 and an error field.
  if (body && body.status === 'error') throw new Error(body.message || 'The backend reported an error.')
  if (body && body.error) throw new Error(body.error)
  return body
}

export async function getHealth() {
  try {
    const res = await fetch(`${BASE}/health`)
    return res.ok ? await res.json() : null
  } catch (e) {
    return null // backend not running
  }
}

export async function uploadLap(file, { driver = 'Driver', track = 'Unknown', car = 'Unknown' } = {}) {
  const form = new FormData()
  form.append('file', file)
  const q = new URLSearchParams({ driver_name: driver, track, car })
  return handle(await fetch(`${BASE}/upload?${q}`, { method: 'POST', body: form }))
}

export async function saveSession(body) {
  return handle(
    await fetch(`${BASE}/profile/session`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  )
}

export async function getProfile(driver) {
  return handle(await fetch(`${BASE}/profile/${encodeURIComponent(driver)}`))
}

export async function askCoach(body) {
  return handle(
    await fetch(`${BASE}/coach/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  )
}

export async function analyzeLap(lapId, referenceLapId) {
  return handle(await fetch(`${BASE}/analyze/${lapId}?reference_lap_id=${referenceLapId}`, { method: 'POST' }))
}

export async function getLap(lapId) {
  return handle(await fetch(`${BASE}/lap/${lapId}`))
}

export async function getLeaderboard(limit = 10) {
  return handle(await fetch(`${BASE}/leaderboard?limit=${limit}`))
}

// Loads a bundled demo lap (frontend/public/demo/...) as a File, ready to upload.
export async function demoFile(name) {
  const res = await fetch(`/demo/${name}`)
  if (!res.ok) throw new Error('Could not load the demo lap files.')
  return new File([await res.blob()], name, { type: 'application/json' })
}
