# VAS Reconciliation System — Implementation TODO

## Phase 0 — Scaffolding
- [x] Create requirements.txt
- [x] Create .env.example
- [x] Create directory structure and __init__.py files
- [x] Create exports/ directory note in .gitkeep

## Phase 1 — Configuration & State Contracts
- [x] config.py — Settings, get_llm(), PARTNER_COLUMN_MAP, get_fields_to_compare()
- [x] graph/state.py — ReconciliationState, MatchedRecord, ReconciliationReport

## Phase 2 — Tools Layer
- [x] tools/excel_parser.py — pandas parsing, column normalization, period inference
- [x] tools/mongo_query.py — async motor queries, cursor-based fetching

## Phase 3 — Graph Nodes
- [x] graph/nodes/file_ingestion.py
- [x] graph/nodes/db_query.py
- [x] graph/nodes/reconciliation.py
- [x] graph/nodes/report_generation.py
- [x] graph/nodes/dispatcher.py

## Phase 4 — Dispatch Branches
- [x] dispatch/excel_export.py — four-sheet workbook
- [x] dispatch/email_report.py — stub
- [x] dispatch/dashboard_push.py — stub

## Phase 5 — Graph Wiring
- [x] graph/graph.py — StateGraph assembly and compile

## Phase 6 — FastAPI App & Frontend
- [x] main.py — endpoints, motor lifecycle, static files
- [x] frontend/index.html — upload UI, state machine, results display

## Phase 7 — Testing
- [x] tests/conftest.py — shared fixtures
- [x] tests/test_file_ingestion.py
- [x] tests/test_reconciliation.py

## Phase 8 — Polish
- [x] Logging throughout nodes
- [x] Tenacity retries on LLM call (3 attempts, exponential backoff, retry logging)
- [x] Startup validation and exports/ dir auto-creation
- [x] Lazy imports for langchain_core in report_generation (same pattern as config.py fix)
