import { useState } from 'react'
import UploadPage  from './pages/UploadPage'
import RunPage     from './pages/RunPage'
import HistoryPage from './pages/HistoryPage'

const TABS = [
  { id: 'upload',  label: '⬆ New Run'     },
  { id: 'history', label: '📋 Run History' },
]

export default function App() {
  const [tab,    setTab]    = useState('upload')
  const [runid,  setRunid]  = useState(null)   // UUID of the active run

  function handleRunCreated(id) {
    setRunid(id)
    setTab('run')
  }

  function handleSelectRun(id) {
    setRunid(id)
    setTab('run')
  }

  return (
    <div>
      {/* Shell bar */}
      <div style={{
        background: '#1C2833', color: 'white',
        padding: '0 1.5rem', height: '3rem',
        display: 'flex', alignItems: 'center', gap: '1rem',
      }}>
        <span style={{ fontWeight: 700, fontSize: '1rem', letterSpacing: '0.03em' }}>
          SAP DMLT Consolidation Study Assistant
        </span>
        <span style={{ marginLeft: 'auto', fontSize: '0.8rem', color: '#90A4AE' }}>
          Formula-driven · AI-enriched · Client-ready
        </span>
      </div>

      {/* Nav tabs */}
      <div style={{ background: '#2E4057', padding: '0 1.5rem' }}>
        <div style={{ display: 'flex', gap: 0 }}>
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                padding: '0.6rem 1.1rem',
                background: 'transparent',
                border: 'none',
                borderBottom: tab === t.id ? '3px solid #048A81' : '3px solid transparent',
                color: tab === t.id ? 'white' : '#B0BEC5',
                cursor: 'pointer',
                fontWeight: tab === t.id ? 700 : 400,
                fontSize: '0.88rem',
                transition: 'color 0.15s',
              }}
            >
              {t.label}
            </button>
          ))}
          {runid && (
            <button
              onClick={() => setTab('run')}
              style={{
                padding: '0.6rem 1.1rem',
                background: 'transparent',
                border: 'none',
                borderBottom: tab === 'run' ? '3px solid #048A81' : '3px solid transparent',
                color: tab === 'run' ? 'white' : '#B0BEC5',
                cursor: 'pointer',
                fontWeight: tab === 'run' ? 700 : 400,
                fontSize: '0.88rem',
              }}
            >
              ▶ Current Run
            </button>
          )}
        </div>
      </div>

      {/* Page content */}
      <div className="dmlt-content">
        {tab === 'upload'  && <UploadPage  onRunCreated={handleRunCreated} />}
        {tab === 'history' && <HistoryPage onSelectRun={handleSelectRun} />}
        {tab === 'run'     && runid && <RunPage runid={runid} />}
      </div>
    </div>
  )
}
