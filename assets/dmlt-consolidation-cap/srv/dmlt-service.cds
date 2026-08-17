using { dmlt } from '../db/schema';

service DmltService @(path: '/dmlt') {

  // ── Runs ──────────────────────────────────────────────────────────────────
  entity Runs as projection on dmlt.Runs
    excluding { sections, results, findings }
    actions {
      // Trigger analysis — called after upload to start the agent
      action startAnalysis() returns { runid: String; status: String; };
    };

  // ── Run results (read-only — written by agent callback) ───────────────────
  @readonly entity CalculationResults as projection on dmlt.CalculationResults;
  @readonly entity AIFindings         as projection on dmlt.AIFindings;

  // ── Custom REST actions (handled in dmlt-service.js) ──────────────────────

  // POST /dmlt/upload  — accepts {sections: {...}} body from programmatic callers
  // (multipart upload is handled by Express middleware at /api/upload)
  action upload(
    sections : LargeString  // JSON-stringified object with keys: master,growth,system,org,nriv
  ) returns { runid: String; status: String; message: String; };

  // POST /dmlt/saveResults  — agent callback to persist calculation results + excel
  action saveResults(
    runid              : String,
    calculationResults : LargeString,
    aiFindings         : LargeString,
    excelBase64        : LargeString
  ) returns { success: Boolean; message: String; };
}
