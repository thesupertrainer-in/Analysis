import { useState, useEffect, useCallback } from 'react'
import { getRunStatus, downloadUrl } from '../api'

const STATUS_STEPS = ['PENDING', 'CALCULATING', 'ANALYSING', 'COMPLETE']

function stepClass(step, currentStatus) {
  if (currentStatus === 'FAILED') return step === 'PENDING' ? 'complete' : 'failed'
  const stepIdx    = STATUS_STEPS.indexOf(step)
  const currentIdx = STATUS_STEPS.indexOf(currentStatus)
  if (stepIdx < currentIdx)  return 'complete'
  if (stepIdx === currentIdx) return 'active'
  return ''
}

export default function RunPage({ runid }) {
  const [run,     setRun]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  const POLL_INTERVAL = 5000

  const fetchStatus = useCallback(async () => {
    try {
      const data = await getRunStatus(runid)
      setRun(data)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [runid])

  useEffect(() => {
    fetchStatus()
    const timer = setInterval(() => {
      if (run && ['COMPLETE', 'FAILED'].includes(run.status)) return
      fetchStatus()
    }, POLL_INTERVAL)
    return () => clearInterval(timer)
  }, [fetchStatus, run?.status])

  if (loading) return <div style={{ padding: '2rem', textAlign: 'center' }}>⏳ Loading run status…</div>
  if (error)   return <div className="msg-error" style={{ marginTop: '1rem' }}>⚠ {error}</div>
  if (!run)    return <div className="msg-error">Run not found.</div>

  const isDone   = run.status === 'COMPLETE'
  const isFailed = run.status === 'FAILED'

  return (
    <div>
      <div className="spacer" />
      <div className="page-title">Run Status</div>
      <div className="page-subtitle">
        Run ID: <code>{run.runid || runid}</code> &nbsp;|&nbsp;
        Systems: <strong>{run.sidcltns || '—'}</strong>
      </div>

      {/* KPI row */}
      <div className="kpi-row">
        <div className="kpi-card">
          <div className="kpi-label">Status</div>
          <div className={`status-badge status-${run.status}`} style={{ fontSize: '1rem', padding: '0.3rem 0.8rem' }}>
            {run.status}
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Systems</div>
          <div className="kpi-value" style={{ fontSize: '1.1rem' }}>
            {run.sidcltns?.split(',').join(', ') || '—'}
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Created</div>
          <div className="kpi-value" style={{ fontSize: '1rem' }}>
            {run.createdAt ? new Date(run.createdAt).toLocaleString() : '—'}
          </div>
        </div>
      </div>

      {/* Progress steps */}
      <div className="progress-steps">
        {STATUS_STEPS.map(step => (
          <div key={step} className={`step ${stepClass(step, run.status)}`}>
            {step === 'PENDING'     && '1. Pending'}
            {step === 'CALCULATING' && '2. Calculating'}
            {step === 'ANALYSING'   && '3. AI Analysis'}
            {step === 'COMPLETE'    && '4. Complete'}
          </div>
        ))}
      </div>

      {/* Active polling indicator */}
      {!isDone && !isFailed && (
        <div className="msg-info">
          ⏳ Analysis in progress — refreshing every 5 seconds…
        </div>
      )}

      {/* Success */}
      {isDone && (
        <div className="msg-ok">
          ✓ Analysis complete! Your Excel report is ready.
        </div>
      )}

      {/* Error */}
      {isFailed && (
        <div className="msg-error">
          ✗ Run failed: {run.errorMessage || 'Unknown error'}
        </div>
      )}

      {/* Download */}
      {isDone && (
        <div style={{ marginTop: '1rem' }}>
          <a
            href={downloadUrl(runid)}
            download
            className="btn-primary"
            style={{ textDecoration: 'none' }}
          >
            ⬇ Download Excel Report
          </a>
        </div>
      )}

      {/* What the report contains */}
      <div className="spacer" /><div className="spacer" />
      <div style={{ background: 'white', borderRadius: 8, padding: '1.25rem', border: '1px solid #e0e0e0' }}>
        <div style={{ fontWeight: 700, marginBottom: '0.75rem', color: '#2E4057' }}>
          Excel Report Contents (9 Sheets)
        </div>
        <table>
          <thead>
            <tr><th>Sheet</th><th>Contents</th></tr>
          </thead>
          <tbody>
            {[
              ['COVER',            'Project details, colour legend, workflow guide'],
              ['SYSTEMS',          'Source system profiles — DB, release, SP level, volumes'],
              ['MAIN',             'All tables × systems — toggle Include? to scope migration'],
              ['COLLISIONS',       'Company-code collisions — same code, different entities'],
              ['CONFLICTS',        'Number-range conflicts — overlapping ranges or level mismatches'],
              ['GROWTH',           'Year-on-year document counts — steep growth & archiving candidates'],
              ['HARDWARE_SIZING',  'Target S/4HANA hardware sizing — formula-driven off MAIN'],
              ['SUMMARY',          'Executive summary — Q1–Q5, all formula-driven'],
              ['DASHBOARD',        'KPI cards + occupied volume chart'],
            ].map(([sheet, desc]) => (
              <tr key={sheet}>
                <td style={{ fontWeight: 600, fontFamily: 'monospace', color: '#048A81' }}>{sheet}</td>
                <td>{desc}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
