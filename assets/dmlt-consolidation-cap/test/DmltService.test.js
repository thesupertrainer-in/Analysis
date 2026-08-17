import cds from '@sap/cds'

cds.test(import.meta.dirname + '/..')

describe('DmltService — upload and run lifecycle', () => {
  let srv, Runs, CalculationResults, AIFindings

  beforeAll(async () => {
    srv                = await cds.connect.to('DmltService')
    Runs               = srv.entities.Runs
    // RunSections is not exposed in the service layer — use the full entity name
    CalculationResults = srv.entities.CalculationResults
    AIFindings         = srv.entities.AIFindings
  })

  // ── Helper — minimal valid section data ─────────────────────────────────
  function makeSections(overrides = {}) {
    return {
      master: [{ runid: 'TEST01', sidclnt: 'SYS_100', tabname: 'BKPF', agg_level: 'T', tab_total_kb: 2048, clnt_count: 5000, category: 'APPL', delv_class: 'A', bukrs: '0001' }],
      growth: [{ runid: 'TEST01', sidclnt: 'SYS_100', tabname: 'BKPF', gjahr: 2023, doc_count: 5000 }],
      system: [{ runid: 'TEST01', sidclnt: 'SYS_100', sid: 'SYS', db_sys: 'HDB', rel: '108', sp_level: '0003', unicode: 'X', addons: '', total_vol: 1000, occupied_vol: 600 }],
      org:    [{ runid: 'TEST01', sidclnt: 'SYS_100', from_type: 'BUKRS', from_id: '0001', to_type: 'CLIENT', to_id: '100', from_text: 'Test Corp' }],
      nriv:   [{ runid: 'TEST01', sidclnt: 'SYS_100', object: 'TESTOBJ', subobject: '', nrrangenr: '01', fromnumber: '0000000001', tonumber: '9999999999', nrlevel: '00000000000000000001', externind: '' }],
      ...overrides,
    }
  }

  // ── Test: upload creates Run and 5 RunSections ───────────────────────────

  it('upload creates a Run with status PENDING and 5 RunSections', async () => {
    const result = await srv.send('upload', { sections: JSON.stringify(makeSections()) })

    expect(result).toHaveProperty('runid')
    expect(result.status).toBe('PENDING')
    expect(result.message).toMatch(/Upload successful/)

    const runID = result.runid

    const run = await SELECT.one.from(Runs).where({ ID: runID })
    expect(run).not.toBeNull()
    expect(run.status).toBe('PENDING')
    expect(run.runid).toBe('TEST01')

    const sections = await SELECT.from('dmlt.RunSections').where({ run_ID: runID })
    expect(sections).toHaveLength(5)

    const sectionNames = sections.map(s => s.section).sort()
    expect(sectionNames).toEqual(['growth', 'master', 'nriv', 'org', 'system'])
  })

  // ── Test: upload rejects missing section ─────────────────────────────────

  it('upload rejects when a section is missing', async () => {
    const secs = makeSections()
    delete secs.nriv

    await expect(
      srv.send('upload', { sections: JSON.stringify(secs) })
    ).rejects.toThrow(/nriv/)
  })

  // ── Test: saveResults marks run COMPLETE ─────────────────────────────────

  it('saveResults persists results and marks run COMPLETE', async () => {
    const uploadResult = await srv.send('upload', { sections: JSON.stringify(makeSections()) })
    const runID = uploadResult.runid

    const calcResults = JSON.stringify([
      { calculationType: 'SIZING', result: { totalRows: 5000, totalKB: 2048 } },
    ])
    const findings = JSON.stringify([
      { section: 'SIZING', findings: [{ type: 'volume', message: 'Test finding' }] },
    ])

    const saveResult = await srv.send('saveResults', {
      runid:              runID,
      calculationResults: calcResults,
      aiFindings:         findings,
      excelBase64:        '',
    })

    expect(saveResult.success).toBe(true)

    const run = await SELECT.one.from(Runs).where({ ID: runID })
    expect(run.status).toBe('COMPLETE')

    const results = await SELECT.from(CalculationResults).where({ run_ID: runID })
    expect(results.length).toBeGreaterThan(0)
    expect(results[0].calculationType).toBe('SIZING')

    const aif = await SELECT.from(AIFindings).where({ run_ID: runID })
    expect(aif.length).toBeGreaterThan(0)
  })

  // ── Test: Runs list returns records ──────────────────────────────────────

  it('Runs entity is queryable and returns records', async () => {
    await INSERT.into(Runs).entries({
      ID: cds.utils.uuid(), runid: 'HISTORY_TEST',
      sidcltns: 'SYS_100', status: 'COMPLETE',
    })
    const runs = await SELECT.from(Runs).limit(5)
    expect(runs.length).toBeGreaterThan(0)
  })
})
