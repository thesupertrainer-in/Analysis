/**
 * Custom CDS server entrypoint — ESM module.
 * Registers multer-based upload middleware before CAP takes over.
 */
import cds      from '@sap/cds'
import express   from 'express'
import multer    from 'multer'
import path      from 'path'
import fs        from 'fs'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const UPLOADS_DIR = process.env.UPLOADS_DIR
  || path.join(__dirname, 'uploads')

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
}

cds.on('bootstrap', (app) => {

  // ── Health probe endpoint ─────────────────────────────────────────────────
  app.get('/health', (_req, res) => res.json({ status: 'UP' }))

  // ── Disable CDS body-parser for multipart upload route ───────────────────
  // CDS applies express.json() globally; multer must read the raw stream.
  // Register a passthrough raw() handler FIRST so CDS doesn't parse it.
  app.use('/api/upload', (req, _res, next) => { req._skipBodyParser = true; next() })

  // ── Custom REST routes — must be registered BEFORE CDS OData router ──────
  // Status and download use lowercase 'runs' to avoid OData interception
  app.get('/api/runs/:runid/status', async (req, res) => {
    try {
      const { runid } = req.params
      const db = cds.db || await cds.connect.to('db')
      const run = await db.run(
        SELECT.one.from('dmlt.Runs')
          .where({ ID: runid })
          .columns('ID', 'runid', 'sidcltns', 'status', 'createdAt', 'errorMessage', 'excelPath')
      )
      if (!run) return res.status(404).json({ error: 'Run not found' })
      const result = { ...run }
      if (run.status === 'COMPLETE' && run.excelPath) {
        result.downloadUrl = `/api/runs/${runid}/download`
      }
      res.json(result)
    } catch (err) {
      res.status(500).json({ error: err.message })
    }
  })

  // Agent callback — POST /api/save-results
  // Uses explicit JSON parser because this route bypasses CDS body-parser
  app.post('/api/save-results', express.json({ limit: '50mb' }), async (req, res) => {
    try {
      const data = req.body || {}
      const srv  = await cds.connect.to('DmltService')
      const result = await srv.send('saveResults', data)
      res.json(result)
    } catch (err) {
      console.error('[DMLT] /api/save-results error:', err.message)
      res.status(500).json({ error: err.message })
    }
  })

  app.get('/api/runs/:runid/download', async (req, res) => {
    try {
      const { runid } = req.params
      const db = cds.db || await cds.connect.to('db')
      const run = await db.run(
        SELECT.one.from('dmlt.Runs')
          .where({ ID: runid })
          .columns('status', 'excelPath', 'runid')
      )
      if (!run)              return res.status(404).json({ error: 'Run not found' })
      if (run.status !== 'COMPLETE')
        return res.status(400).json({ error: `Run not complete (${run.status})` })
      if (!run.excelPath || !fs.existsSync(run.excelPath))
        return res.status(404).json({ error: 'Excel file not found' })
      res.setHeader('Content-Type',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
      res.setHeader('Content-Disposition',
        `attachment; filename="dmlt_report_${run.runid}.xlsx"`)
      fs.createReadStream(run.excelPath).pipe(res)
    } catch (err) { res.status(500).json({ error: err.message }) }
  })


  ensureDir(UPLOADS_DIR)

  // Use memory storage — handler reads buffer directly; service writes files later
  const storage = multer.memoryStorage()
  // Accept any field name — section detected from field name, filename, or JSON content
  const SECTION_NAMES = ['master', 'growth', 'system', 'org', 'nriv']
  const uploadAny = multer({ storage }).any()

  // Multipart upload endpoint — processes 5 JSON files and calls service
  app.post('/api/upload', (req, res, next) => {
    uploadAny(req, res, (err) => {
      if (err) {
        console.error('[DMLT] multer error:', err)
        return res.status(400).json({ error: `File upload error: ${err.message}` })
      }
      next()
    })
  }, async (req, res) => {
    try {
      const files = req.files || []
      if (files.length === 0) {
        return res.status(400).json({ error: 'No files uploaded' })
      }

      const sections = {}
      for (const file of files) {
        // Detect section from: field name → filename → JSON 'section' field
        let name = SECTION_NAMES.includes(file.fieldname) ? file.fieldname : null
        if (!name) {
          const base = path.basename(file.originalname, '.json').toLowerCase()
          name = SECTION_NAMES.find(s => base.endsWith(`_${s}`) || base === s || base.includes(s))
        }
        const raw = file.buffer
          ? file.buffer.toString('utf-8')
          : fs.readFileSync(file.path, 'utf-8')
        if (!name) {
          const parsed = JSON.parse(raw)
          name = (parsed.section || '').toLowerCase()
        }
        if (!name || !SECTION_NAMES.includes(name)) {
          return res.status(400).json({ error: `Cannot detect section for file: ${file.originalname}` })
        }
        const parsed = JSON.parse(raw)
        sections[name] = Array.isArray(parsed) ? parsed : (parsed.data || parsed)
      }

      const srv = await cds.connect.to('DmltService')
      // CDS action declares sections as LargeString — must JSON.stringify before send
      const result = await srv.send('upload', { sections: JSON.stringify(sections) })

      return res.json(result)
    } catch (err) {
      console.error('[DMLT] /api/upload error:', err)
      res.status(500).json({ error: err.message })
    }
  })
})

export default cds.server
