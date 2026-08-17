import { useState, useEffect } from 'react'
import { listRuns, downloadUrl } from '../api'

const STATUS_COLORS = {
  PENDING:     '#1565C0',
  CALCULATING: '#BF8F00',
  ANALYSING:   '#BF8F00',
  COMPLETE:    '#2E7D32',
  FAILED:      '#B71C1C',
}

export default function HistoryPage({ onSelectRun }) {
  const [runs,    setRuns]    = useState([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  useEffect(() => {
    listRuns()
      .then(setRuns)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div style={{ padding: '2rem', textAlign: 'center' }}>⏳ Loading run history…</div>
  if (error)   return <div className="msg-error" style={{ marginTop: '1rem' }}>⚠ {error}</div>

  return (
    <div>
      <div className="spacer" />
      <div className="page-title">Run History</div>
      <div className="page-subtitle">
        All past analysis runs — click a row to view details or download the report.
      </div>

      {runs.length === 0 ? (
        <div className="msg-info">No runs yet. Go to "New Run" to upload files and start an analysis.</div>
      ) : (
        <div className="run-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Systems</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {runs.map(run => (
                <tr
                  key={run.ID}
                  style={{ cursor: 'pointer' }}
                  onClick={() => onSelectRun(run.ID)}
                >
                  <td style={{ fontFamily: 'monospace', fontSize: '0.82rem' }}>
                    {run.runid || run.ID.slice(0, 8) + '…'}
                  </td>
                  <td>{run.sidcltns || '—'}</td>
                  <td>
                    <span className={`status-badge status-${run.status}`}>
                      {run.status}
                    </span>
                  </td>
                  <td style={{ color: '#546E7A', fontSize: '0.82rem' }}>
                    {run.createdAt ? new Date(run.createdAt).toLocaleString() : '—'}
                  </td>
                  <td onClick={e => e.stopPropagation()}>
                    {run.status === 'COMPLETE' && (
                      <a
                        href={downloadUrl(run.ID)}
                        download
                        className="btn-secondary"
                        style={{ textDecoration: 'none', padding: '0.3rem 0.75rem', fontSize: '0.82rem' }}
                      >
                        ⬇ Excel
                      </a>
                    )}
                    {run.status === 'FAILED' && (
                      <span className="text-muted" title={run.errorMessage}>✗ Failed</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
