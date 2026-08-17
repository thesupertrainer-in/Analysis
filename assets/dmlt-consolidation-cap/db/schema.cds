namespace dmlt;

using { cuid, managed } from '@sap/cds/common';

// ─── Run ────────────────────────────────────────────────────────────────────
// One record per analysis run (set of 5 JSON files)
entity Runs : cuid, managed {
  runid         : String(100);         // runid from the JSON files
  exportedOn    : String(30);          // exported_on from JSON
  sidcltns      : String(500);         // comma-separated sidclnt values
  status        : String(20)           // PENDING|INGESTING|CALCULATING|ANALYSING|COMPLETE|FAILED
                  default 'PENDING';
  errorMessage  : LargeString;
  excelPath     : String(500);         // path to generated xlsx on disk
  sections      : Composition of many RunSections on sections.run = $self;
  results       : Composition of many CalculationResults on results.run = $self;
  findings      : Composition of many AIFindings on findings.run = $self;
}

// ─── RunSections ────────────────────────────────────────────────────────────
// Stores raw JSON data for each of the 5 sections
entity RunSections : cuid {
  run         : Association to Runs;
  section     : String(20);     // master|growth|system|org|nriv
  rawData     : LargeString;    // JSON array as string
  recordCount : Integer;
}

// ─── CalculationResults ─────────────────────────────────────────────────────
entity CalculationResults : cuid {
  run             : Association to Runs;
  calculationType : String(30);   // SIZING|COLLISIONS|CONFLICTS|GROWTH|SYSTEM_PROFILES
  resultJson      : LargeString;
  calculatedAt    : Timestamp;
}

// ─── AIFindings ─────────────────────────────────────────────────────────────
entity AIFindings : cuid {
  run          : Association to Runs;
  section      : String(30);
  findingsJson : LargeString;
  generatedAt  : Timestamp;
}
