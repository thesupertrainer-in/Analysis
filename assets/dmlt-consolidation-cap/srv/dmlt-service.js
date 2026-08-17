import cds  from '@sap/cds'
import path  from 'path'
import fs    from 'fs'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

const UPLOADS_DIR = process.env.UPLOADS_DIR
  || path.join(__dirname, '..', 'uploads')
const AGENT_URL   = process.env.AGENT_URL || 'http://localhost:8000'

const REQUIRED_SECTIONS = ['master', 'growth', 'system', 'org', 'nriv']

const SECTION_FIELDS = {
  master: ['sidclnt', 'tabname', 'agg_level', 'tab_total_kb', 'clnt_count'],
  growth: ['sidclnt', 'tabname', 'gjahr', 'doc_count'],
  system: ['sidclnt', 'sid', 'db_sys', 'rel', 'occupied_vol', 'total_vol'],
  org:    ['sidclnt', 'from_type', 'from_id', 'to_type', 'from_text'],
  nriv:  ['sidclnt', 'object', 'nrrangenr', 'fromnumber', 'tonumber', 'nrlevel'],
}

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
}

function validateSection(name, data) {
  const errors = []
  if (!Array.isArray(data) || data.length === 0) {
    errors.push({ section: name, message: 'Section is empty or not an array' })
    return errors
  }
  const required = SECTION_FIELDS[name] || []
  const sample   = data[0]
  for (const field of required) {
    if (!(field in sample)) {
      errors.push({ section: name, message: `Missing required field: ${field}` })
    }
  }
  return errors
}

async function callAgent(runPayload) {
  const resp = await fetch(`${AGENT_URL}/invoke`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ message: JSON.stringify(runPayload) }),
  })
  if (!resp.ok) {
    const txt = await resp.text()
    throw new Error(`Agent returned ${resp.status}: ${txt}`)
  }
  return resp.json()
}

export default class DmltService extends cds.ApplicationService {

  async init() {
    const { Runs, CalculationResults, AIFindings } = this.entities
    // RunSections is not exposed in the service — access via full entity name
    const RunSections = 'dmlt.RunSections'

    // ── upload action ─────────────────────────────────────────────────────
    this.on('upload', async (req) => {
      const body     = req.data || {}
      // sections may arrive as a JSON string (from CDS action) or as an object (internal)
      let sections   = body.sections
      if (typeof sections === 'string') {
        try { sections = JSON.parse(sections) } catch { /* invalid JSON */ }
      }
      if (!sections || typeof sections !== 'object') sections = body

      // Validate all 5 sections present
      const missing = REQUIRED_SECTIONS.filter(s => !(s in sections))
      if (missing.length > 0) {
        return req.reject(400,
          `Missing sections: ${missing.join(', ')}. All 5 required: ${REQUIRED_SECTIONS.join(', ')}.`)
      }

      // Field-level validation
      const validationErrors = []
      for (const secName of REQUIRED_SECTIONS) {
        validationErrors.push(...validateSection(secName, sections[secName]))
      }
      if (validationErrors.length > 0) {
        return req.reject(400, JSON.stringify({ errors: validationErrors }))
      }

      // Derive metadata
      const systemRows = sections.system || []
      const sidcltns   = [...new Set(systemRows.map(r => r.sidclnt))].sort()
      const runidRaw   = sections.master?.[0]?.runid
        || sections.system?.[0]?.runid
        || `RUN_${Date.now()}`
      const exportedOn = sections.master?.[0]?.exported_on || ''

      // Create Run record
      const runUUID = cds.utils.uuid()
      await INSERT.into(Runs).entries({
        ID: runUUID, runid: runidRaw, exportedOn,
        sidcltns: sidcltns.join(','), status: 'PENDING',
      })

      // Persist sections
      await INSERT.into(RunSections).entries(
        REQUIRED_SECTIONS.map(s => ({
          ID: cds.utils.uuid(), run_ID: runUUID,
          section: s, rawData: JSON.stringify(sections[s]),
          recordCount: sections[s].length,
        }))
      )

      // Save JSON files for agent
      const runDir = path.join(UPLOADS_DIR, runidRaw)
      ensureDir(runDir)
      for (const secName of REQUIRED_SECTIONS) {
        fs.writeFileSync(
          path.join(runDir, `${secName}.json`),
          JSON.stringify({ runid: runidRaw, section: secName, data: sections[secName] })
        )
      }

      return { runid: runUUID, status: 'PENDING', message: 'Upload successful. Call startAnalysis to begin.' }
    })

    // ── startAnalysis (bound action on Runs) ─────────────────────────────
    this.on('startAnalysis', Runs, async (req) => {
      const runID = req.params[0]?.ID || req.params[0]
      const run   = await SELECT.one.from(Runs).where({ ID: runID })

      if (!run) return req.reject(404, `Run ${runID} not found`)
      if (run.status === 'COMPLETE') return req.reject(409, `Run ${runID} is already complete`)
      if (['CALCULATING', 'ANALYSING'].includes(run.status)) {
        return req.reject(409, `Run ${runID} is already in progress`)
      }

      const sectionRows = await SELECT.from(RunSections)
        .where({ run_ID: runID }).columns('section', 'rawData')

      const sections = {}
      for (const row of sectionRows) {
        try { sections[row.section] = JSON.parse(row.rawData) } catch { sections[row.section] = [] }
      }

      await UPDATE(Runs, runID).with({ status: 'CALCULATING' })

      const runPayload = {
        runid:    run.runid,
        run_ID:   runID,
        sidcltns: run.sidcltns?.split(',') || [],
        sections,
        callbackUrl: `${process.env.CAP_URL || 'http://localhost:4004'}/api/save-results`,
      }

      callAgent(runPayload).catch(async (err) => {
        console.error('[DMLT] Agent call failed:', err.message)
        await UPDATE(Runs, runID).with({
          status: 'FAILED', errorMessage: `Agent call failed: ${err.message}`,
        })
      })

      return { runid: runID, status: 'CALCULATING' }
    })

    // ── saveResults (agent callback) ────────────────────────────────────
    this.on('saveResults', async (req) => {
      const { runid, calculationResults, aiFindings, excelBase64 } = req.data
      if (!runid) return req.reject(400, 'runid is required')

      const run = await SELECT.one.from(Runs).where({ ID: runid })
        || await SELECT.one.from(Runs).where({ runid })
      if (!run) return req.reject(404, `Run ${runid} not found`)

      const runUUID = run.ID

      try {
        if (calculationResults) {
          const results = JSON.parse(calculationResults)
          if (Array.isArray(results) && results.length > 0) {
            await INSERT.into(CalculationResults).entries(
              results.map(r => ({
                ID: cds.utils.uuid(), run_ID: runUUID,
                calculationType: r.calculationType,
                resultJson: JSON.stringify(r.result),
                calculatedAt: new Date().toISOString(),
              }))
            )
          }
        }

        if (aiFindings) {
          const findings = JSON.parse(aiFindings)
          if (Array.isArray(findings) && findings.length > 0) {
            await INSERT.into(AIFindings).entries(
              findings.map(f => ({
                ID: cds.utils.uuid(), run_ID: runUUID,
                section: f.section, findingsJson: JSON.stringify(f.findings),
                generatedAt: new Date().toISOString(),
              }))
            )
          }
        }

        let excelPath = null
        if (excelBase64) {
          const runDir = path.join(UPLOADS_DIR, run.runid)
          ensureDir(runDir)
          excelPath = path.join(runDir, 'report.xlsx')
          fs.writeFileSync(excelPath, Buffer.from(excelBase64, 'base64'))
        }

        await UPDATE(Runs, runUUID).with({ status: 'COMPLETE', excelPath })
        return { success: true, message: 'Results saved successfully' }

      } catch (err) {
        await UPDATE(Runs, runUUID).with({
          status: 'FAILED', errorMessage: err.message,
        })
        return { success: false, message: err.message }
      }
    })

    // Note: /api/runs/:runid/status and /api/runs/:runid/download
    // are registered in server.js (bootstrap phase) to avoid OData interception.

    await super.init()
  }
}
