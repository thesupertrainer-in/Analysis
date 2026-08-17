/**
 * API client — all calls to the CAP backend go through here.
 */
const BASE = ''   // same origin

export async function uploadFiles(fileMap) {
  // fileMap: { master: File, growth: File, system: File, org: File, nriv: File }
  const form = new FormData()
  for (const [section, file] of Object.entries(fileMap)) {
    form.append(section, file)
  }
  const res = await fetch(`${BASE}/api/upload`, { method: 'POST', body: form })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || `Upload failed (${res.status})`)
  return data
}

export async function startAnalysis(runid) {
  const res = await fetch(`${BASE}/dmlt/Runs(${runid})/startAnalysis`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({}),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error?.message || data.message || `Start failed (${res.status})`)
  return data.value || data
}

export async function getRunStatus(runid) {
  const res = await fetch(`${BASE}/api/runs/${runid}/status`)
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || `Status check failed (${res.status})`)
  return data
}

export async function listRuns(top = 50) {
  const res = await fetch(
    `${BASE}/dmlt/Runs?$orderby=createdAt desc&$top=${top}&$select=ID,runid,sidcltns,status,createdAt,excelPath,errorMessage`
  )
  const data = await res.json()
  if (!res.ok) throw new Error(data.error?.message || 'Failed to list runs')
  return data.value || []
}

export function downloadUrl(runid) {
  return `${BASE}/api/runs/${runid}/download`
}
