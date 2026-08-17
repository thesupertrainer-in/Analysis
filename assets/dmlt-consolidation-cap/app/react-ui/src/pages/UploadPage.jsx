import { useState, useRef } from 'react'
import { uploadFiles, startAnalysis } from '../api'

const SECTIONS = ['master', 'growth', 'system', 'org', 'nriv']

const SECTION_INFO = {
  master: 'Table volumes (agg_level, tab_total_kb …)',
  growth: 'Year-on-year document counts (gjahr, doc_count …)',
  system: 'System profiles (db_sys, rel, occupied_vol …)',
  org:    'Org structure edges (from_type, from_id …)',
  nriv:   'Number range intervals (object, fromnumber …)',
}

export default function UploadPage({ onRunCreated }) {
  const [fileMap,   setFileMap]   = useState({})   // { section: File }
  const [parsed,    setParsed]    = useState({})   // { section: { count, error } }
  const [uploading, setUploading] = useState(false)
  const [error,     setError]     = useState(null)
  const [phase,     setPhase]     = useState('idle') // idle | selecting | ready | running
  const fileInputRef = useRef()

  // Parse a single file and detect section name from JSON content
  async function parseFile(file) {
    return new Promise((resolve) => {
      const reader = new FileReader()
      reader.onload = (e) => {
        try {
          const doc  = JSON.parse(e.target.result)
          const data = doc.data || doc
          const sec  = (doc.section || '').toLowerCase()
          resolve({ section: sec, count: Array.isArray(data) ? data.length : 0, error: null })
        } catch {
          resolve({ section: null, count: 0, error: 'Invalid JSON' })
        }
      }
      reader.readAsText(file)
    })
  }

  async function handleFileChange(e) {
    const files = [...(e.target.files || [])]
    if (!files.length) return
    setError(null)
    setPhase('selecting')
    await processFiles(files)
    setPhase('ready')
  }

  async function processFiles(files) {
    const newFileMap = { ...fileMap }
    const newParsed  = { ...parsed }
    for (const file of files) {
      const result = await parseFile(file)
      if (result.section && SECTIONS.includes(result.section)) {
        newFileMap[result.section] = file
        newParsed[result.section]  = result
      } else if (result.error) {
        setError(`${file.name}: ${result.error}`)
      } else {
        const nameLower = file.name.toLowerCase()
        const matched   = SECTIONS.find(s => nameLower.includes(s))
        if (matched) {
          newFileMap[matched] = file
          newParsed[matched]  = { ...result, section: matched }
        } else {
          setError(`Cannot detect section for: ${file.name}. Filename or JSON must include master/growth/system/org/nriv.`)
        }
      }
    }
    setFileMap(newFileMap)
    setParsed(newParsed)
  }

  const allReady = SECTIONS.every(s => fileMap[s] && !parsed[s]?.error)

  // Called when user clicks the hero "Start Analysis" button
  function handleStartClick() {
    if (phase === 'idle') {
      // First click → open file picker
      fileInputRef.current?.click()
    } else if (phase === 'ready' && allReady) {
      // All files loaded → run analysis
      runAnalysis()
    } else {
      // Some files missing → open picker again to add more
      fileInputRef.current?.click()
    }
  }

  async function runAnalysis() {
    setError(null)
    setUploading(true)
    setPhase('running')
    try {
      const result = await uploadFiles(fileMap)
      await startAnalysis(result.runid)
      onRunCreated(result.runid)
    } catch (err) {
      setError(err.message)
      setPhase('ready')
    } finally {
      setUploading(false)
    }
  }

  function handleClear() {
    setFileMap({})
    setParsed({})
    setError(null)
    setPhase('idle')
  }

  // Button label and state
  const btnLabel = uploading
    ? '⏳ Uploading & starting…'
    : phase === 'idle'
    ? '▶ Start Analysis'
    : phase === 'selecting'
    ? '⏳ Reading files…'
    : allReady
    ? '▶ Run Analysis Now'
    : '+ Add Missing Files'

  const btnDisabled = uploading || phase === 'selecting' || phase === 'running'

  return (
    <div>
      <div className="spacer" />
      <div className="page-title">DMLT Consolidation Analysis</div>
      <div className="page-subtitle">
        Click <strong>Start Analysis</strong> to select your 5 JSON extract files and begin the analysis pipeline.
        The agent will run deterministic calculations, apply AI reasoning, and generate a 9-sheet Excel report.
      </div>

      {/* Hidden file input — opened programmatically */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".json"
        multiple
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />

      {/* Hero action button */}
      <div className="spacer" />
      <div className="flex-row" style={{ justifyContent: 'center' }}>
        <button
          className="btn-primary"
          style={{ fontSize: '1.05rem', padding: '0.7rem 2rem', minWidth: 220 }}
          disabled={btnDisabled}
          onClick={handleStartClick}
        >
          {btnLabel}
        </button>
        {phase !== 'idle' && !uploading && (
          <button className="btn-secondary" onClick={handleClear}>
            ✕ Clear
          </button>
        )}
      </div>

      {/* Per-section status grid — only shown after files are selected */}
      {phase !== 'idle' && (
        <>
          <div className="spacer" />
          <div style={{ fontWeight: 600, color: '#2E4057', marginBottom: '0.5rem' }}>
            File Status
          </div>
          <div className="section-grid">
            {SECTIONS.map(sec => {
              const info  = parsed[sec]
              const state = !info ? 'empty' : info.error ? 'error' : 'ok'
              return (
                <div key={sec} className={`section-card ${state}`}>
                  <div className="section-name">{sec}</div>
                  {state === 'ok' && (
                    <>
                      <div className="section-count">✓ {info.count?.toLocaleString()} rows</div>
                      <div className="section-count" style={{ color: '#78909C' }}>
                        {fileMap[sec]?.name}
                      </div>
                    </>
                  )}
                  {state === 'empty' && (
                    <div className="section-count" style={{ color: '#B0BEC5' }}>
                      ⬜ {SECTION_INFO[sec]}
                    </div>
                  )}
                  {state === 'error' && (
                    <div className="section-error">✗ {info.error}</div>
                  )}
                </div>
              )
            })}
          </div>

          {/* Validation messages */}
          {error && (
            <>
              <div className="spacer" />
              <div className="msg-error">⚠ {error}</div>
            </>
          )}

          {allReady && !uploading && (
            <div className="msg-ok" style={{ marginTop: '1rem' }}>
              ✓ All 5 sections ready — click <strong>Run Analysis Now</strong> to begin.
            </div>
          )}

          {!allReady && !error && phase === 'ready' && (
            <div className="msg-info" style={{ marginTop: '1rem' }}>
              {SECTIONS.filter(s => !fileMap[s]).length} file(s) still missing —
              click <strong>Add Missing Files</strong> to select them.
            </div>
          )}
        </>
      )}

      {/* How it works */}
      <div className="spacer" /><div className="spacer" />
      <div style={{ background: 'white', borderRadius: 8, padding: '1.25rem', border: '1px solid #e0e0e0' }}>
        <div style={{ fontWeight: 700, marginBottom: '0.75rem', color: '#2E4057' }}>
          How It Works
        </div>
        <div className="progress-steps">
          {['1. Select Files', '2. Upload & Validate', '3. Calculate', '4. AI Analysis', '5. Excel Report'].map((s, i) => (
            <div key={i} className="step">{s}</div>
          ))}
        </div>
        <div className="text-muted" style={{ marginTop: '0.75rem' }}>
          Select your 5 JSON extracts (master, growth, system, org, nriv). The agent runs
          deterministic calculations first — sizing, company-code collisions, number-range conflicts,
          growth trends, system profiles — then applies AI reasoning to generate risk findings.
          All outputs land in a 9-sheet Excel workbook.
        </div>
      </div>
    </div>
  )
}
