/**
 * Registers multipart/form-data upload middleware and the
 * POST /dmlt/upload-files REST endpoint.
 *
 * This module is required by server.js (the custom CDS entrypoint).
 */
const path   = require('path')
const fs     = require('fs')
const multer = require('multer')
const cds    = require('@sap/cds')

const UPLOADS_DIR = process.env.UPLOADS_DIR
  || path.join(__dirname, '..', 'uploads')

const REQUIRED_SECTIONS = ['master', 'growth', 'system', 'org', 'nriv']

const SECTION_FIELDS = {
  master: ['sidclnt', 'tabname', 'agg_level'],
  growth: ['sidclnt', 'tabname', 'gjahr', 'doc_count'],
  system: ['sidclnt', 'sid'],
  org:    ['sidclnt', 'from_type', 'from_id'],
  nriv:  ['sidclnt', 'object', 'nrrangenr'],
}

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
}

// Keep files in memory — we parse them immediately
const storage = multer.memoryStorage()
const upload  = multer({
  storage,
  limits: { fileSize: 500 * 1024 * 1024 }, // 500 MB per file
})

module.exports = (app) => {
  // ── POST /api/upload — accepts 5 JSON files (field names = section names) ──
  app.post(
    '/api/upload',
    upload.fields(REQUIRED_SECTIONS.map(s => ({ name: s, maxCount: 1 }))),
    async (req, res) => {
      try {
        const files = req.files || {}
        const sections = {}

        // Parse each file
        for (const secName of REQUIRED_SECTIONS) {
          const fileArr = files[secName]
          if (!fileArr || fileArr.length === 0) continue
          const buf = fileArr[0].buffer
          let parsed
          try {
            parsed = JSON.parse(buf.toString('utf8'))
          } catch {
            return res.status(400).json({
              error: `File for section '${secName}' is not valid JSON`,
            })
          }
          // Accept { section, data: [...] } or { section, data } or bare array
          const data = parsed.data || parsed
          if (!Array.isArray(data)) {
            return res.status(400).json({
              error: `Section '${secName}': data must be a JSON array`,
            })
          }
          sections[secName] = data
        }

        // Check all 5 sections present
        const missing = REQUIRED_SECTIONS.filter(s => !(s in sections))
        if (missing.length > 0) {
          return res.status(400).json({
            error: `Missing sections: ${missing.join(', ')}`,
            required: REQUIRED_SECTIONS,
          })
        }

        // Field validation
        const errors = []
        for (const secName of REQUIRED_SECTIONS) {
          const reqFields = SECTION_FIELDS[secName] || []
          const sample    = sections[secName][0] || {}
          for (const f of reqFields) {
            if (!(f in sample)) {
              errors.push({ section: secName, message: `Missing field: ${f}` })
            }
          }
        }
        if (errors.length > 0) {
          return res.status(400).json({ error: 'Validation failed', errors })
        }

        // Derive metadata
        const systemRows = sections.system || []
        const sidcltns   = [...new Set(systemRows.map(r => r.sidclnt))].sort()
        const runidRaw   = sections.master?.[0]?.runid
          || sections.system?.[0]?.runid
          || `RUN_${Date.now()}`
        const exportedOn = sections.master?.[0]?.exported_on || ''

        // Save to DB via CDS action
        const dmltService = await cds.connect.to('DmltService')
        const runUUID     = cds.utils.uuid()
        const { Runs, RunSections } = dmltService.entities

        await INSERT.into(Runs).entries({
          ID: runUUID, runid: runidRaw, exportedOn,
          sidcltns: sidcltns.join(','), status: 'PENDING',
        })

        await INSERT.into(RunSections).entries(
          REQUIRED_SECTIONS.map(s => ({
            ID: cds.utils.uuid(), run_ID: runUUID,
            section: s, rawData: JSON.stringify(sections[s]),
            recordCount: sections[s].length,
          }))
        )

        // Persist JSON files for agent
        const runDir = path.join(UPLOADS_DIR, runidRaw)
        ensureDir(runDir)
        for (const secName of REQUIRED_SECTIONS) {
          fs.writeFileSync(
            path.join(runDir, `${secName}.json`),
            JSON.stringify({ runid: runidRaw, section: secName, data: sections[secName] })
          )
        }

        res.json({
          runid:     runUUID,
          runidRaw,
          sidcltns,
          status:    'PENDING',
          sections:  Object.fromEntries(
            REQUIRED_SECTIONS.map(s => [s, sections[s].length])
          ),
          message:   'Upload successful. POST to /api/runs/:runid/start to begin analysis.',
        })
      } catch (err) {
        console.error('[upload]', err)
        res.status(500).json({ error: err.message })
      }
    }
  )
}
