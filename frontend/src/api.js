// All calls to the backend live here, so the rest of the app never touches fetch directly.

async function handle(res) {
  if (res.ok) return res.json()
  let detail = `Request failed (${res.status})`
  try {
    const body = await res.json()
    if (body.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
  } catch (e) {
    /* keep the default message */
  }
  throw new Error(detail)
}

export async function getHealth() {
  try {
    return await handle(await fetch('/api/health'))
  } catch (e) {
    return null // backend not running
  }
}

export async function loadSample() {
  return handle(await fetch('/api/sample'))
}

export async function analyzeFiles(lapFile, refFile) {
  const form = new FormData()
  form.append('lap', lapFile)
  if (refFile) form.append('reference', refFile)
  return handle(await fetch('/api/analyze', { method: 'POST', body: form }))
}

export async function sendChat(analysisId, message, history) {
  return handle(
    await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ analysis_id: analysisId, message, history }),
    }),
  )
}
