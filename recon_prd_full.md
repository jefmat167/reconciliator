# VAS Reconciliation System
## Product Requirements Document (PRD)
**Version:** 1.1  
**Status:** Ready for Implementation  
**Prepared for:** Claude Code  

---

## 1. Overview

### 1.1 Purpose
This document specifies the complete requirements for a multi-agent VAS (Value Added Services) transaction reconciliation system. The system automates the end-of-month reconciliation process between a partner provider's transaction records and internal records stored in MongoDB, eliminating the need for manual database queries and custom comparison scripts.

### 1.2 Problem Statement
At the end of each month, the sales team receives an Excel file from a VAS partner containing all transactions recorded on the partner's end. This must be compared against internal transaction records for the same period. Currently, an engineer must manually pull records from MongoDB and write a bespoke comparison script each time. This is time-consuming, error-prone, and creates a dependency on engineering for a routine business operation.

### 1.3 Solution Summary
A LangGraph-powered multi-agent pipeline that:
1. Accepts an uploaded Excel file via a web UI
2. Parses and normalizes partner transaction records
3. Queries MongoDB for internal records covering the same period
4. Performs a two-pass deterministic reconciliation on `referenceId`:
   - **Pass 1:** Set-based diff to identify missing transactions on either side
   - **Pass 2:** Field-level comparison on matched transactions to surface value mismatches
5. Generates a structured report with a natural language summary
6. Exports the results as a downloadable Excel file

---

## 2. Scope

### 2.1 In Scope (v1.0)
- Web UI for file upload and reconciliation trigger
- Multi-agent pipeline (LangGraph + LangChain)
- MongoDB query agent
- Two-pass reconciliation logic engine
- LLM-powered report generation with switchable provider support
- Excel export of reconciliation results (four sheets)
- Period inference from uploaded file (advisory — non-blocking)
- Basic status/progress feedback on the UI

### 2.2 Out of Scope (Planned for Future Releases)
- **v1.1 — Email dispatch:** Automatically email the reconciliation report to the sales team via SendGrid or SMTP upon completion.
- **v1.2 — Web dashboard:** An interactive reconciliation dashboard showing match rates, trend charts, and discrepancy drill-down views, replacing the static export flow.
- Multi-partner reconciliation (currently single partner/product)
- Authentication and role-based access control
- Scheduled/automated reconciliation runs
- Historical reconciliation audit trail

---

## 3. System Architecture

### 3.1 High-Level Architecture

```
[Sales Team Browser]
       |
       | POST /upload (multipart Excel)
       v
[FastAPI Backend]
       |
       | graph.ainvoke(initial_state)
       v
[LangGraph StateGraph]
  |
  |-- Node 1: File Ingestion Agent
  |-- Node 2: DB Query Agent
  |-- Node 3: Reconciliation Agent  (Pass 1: set diff + Pass 2: field comparison)
  |-- Node 4: Report Generation Agent (LLM)
  |-- Node 5: Output Dispatcher
         |
         |-- Branch A: Excel Export      ← ACTIVE (v1.0)
         |-- Branch B: Email Report      ← STUB (v1.1)
         |-- Branch C: Web Dashboard     ← STUB (v1.2)
```

### 3.2 Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI |
| Agent orchestration | LangGraph (`StateGraph`) |
| Agent/tool framework | LangChain |
| Excel parsing | pandas + openpyxl |
| MongoDB driver | motor (async) |
| Excel export | openpyxl |
| LLM abstraction | LangChain `BaseChatModel` (provider-switchable) |
| LLM providers | Groq (default), Anthropic, OpenAI (via config) |
| Frontend | Plain HTML + Vanilla JS (single page) |
| Config management | python-dotenv + Pydantic Settings |

### 3.3 Shared State Schema

All LangGraph nodes communicate through a single `TypedDict`:

```python
from dataclasses import dataclass

@dataclass
class MatchedRecord:
    referenceId: str
    partner_data: dict
    internal_data: dict
    discrepancies: dict   # {field: {"partner": val, "ours": val}}
    has_discrepancy: bool

class ReconciliationState(TypedDict):
    uploaded_file: bytes                  # Raw bytes from the uploaded Excel file
    period: dict                          # {"start": date, "end": date} — inferred from file
    partner_records: list[dict]           # Parsed & normalized rows from Excel
    internal_records: list[dict]          # Records pulled from MongoDB
    missing_in_ours: list[dict]           # In partner file, absent in internal DB
    missing_in_partner: list[dict]        # In internal DB, absent in partner file
    matched_records: list[MatchedRecord]  # All matched records with discrepancy flags
    report: dict                          # Structured report from report generation agent
    outputs_sent: list[str]               # Tracks which dispatch branches succeeded
    errors: list[str]                     # Per-branch errors (non-fatal, for UI display)
```

---

## 4. Detailed Requirements

### 4.1 Project Structure

```
vas-reconciliation/
├── main.py                        # FastAPI app entry point
├── config.py                      # Settings, LLM provider factory
├── graph/
│   ├── __init__.py
│   ├── state.py                   # ReconciliationState TypedDict + MatchedRecord
│   ├── graph.py                   # LangGraph StateGraph wiring
│   └── nodes/
│       ├── __init__.py
│       ├── file_ingestion.py
│       ├── db_query.py
│       ├── reconciliation.py
│       ├── report_generation.py
│       └── dispatcher.py
├── dispatch/
│   ├── __init__.py
│   ├── excel_export.py            # ACTIVE — v1.0
│   ├── email_report.py            # STUB — v1.1
│   └── dashboard_push.py         # STUB — v1.2
├── tools/
│   ├── __init__.py
│   ├── excel_parser.py            # LangChain tool wrapper for pandas
│   └── mongo_query.py             # LangChain tool wrapper for motor
├── frontend/
│   └── index.html                 # Single-page upload + results UI
├── tests/
│   ├── test_file_ingestion.py
│   ├── test_reconciliation.py
│   └── fixtures/
│       └── sample_partner_file.xlsx
├── .env.example
├── requirements.txt
└── README.md
```

### 4.2 Configuration & LLM Provider Switching

**File: `config.py`**

The system must support hot-swapping LLM providers without code changes. Provider selection is controlled entirely through environment variables.

```python
# .env.example
LLM_PROVIDER=groq                     # Options: groq | anthropic | openai
LLM_MODEL=llama3-70b-8192             # Provider-specific model name
GROQ_API_KEY=your_groq_key
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key

MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=your_db_name
MONGODB_COLLECTION=transactions

EXPORT_OUTPUT_DIR=./exports

# Reconciliation config
FIELDS_TO_COMPARE=amount,status       # Comma-separated fields for field-level comparison
```

**Provider factory function:**

```python
from langchain_groq import ChatGroq
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    llm_provider: str = "groq"
    llm_model: str = "llama3-70b-8192"
    groq_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    mongodb_uri: str
    mongodb_db: str
    mongodb_collection: str
    export_output_dir: str = "./exports"
    fields_to_compare: str = "amount,status"

    class Config:
        env_file = ".env"

settings = Settings()

def get_llm():
    if settings.llm_provider == "groq":
        return ChatGroq(model=settings.llm_model, api_key=settings.groq_api_key)
    elif settings.llm_provider == "anthropic":
        return ChatAnthropic(model=settings.llm_model, api_key=settings.anthropic_api_key)
    elif settings.llm_provider == "openai":
        return ChatOpenAI(model=settings.llm_model, api_key=settings.openai_api_key)
    else:
        raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")

def get_fields_to_compare() -> list[str]:
    return [f.strip() for f in settings.fields_to_compare.split(",")]
```

**Provider reference table:**

| Provider | `LLM_PROVIDER` | Recommended `LLM_MODEL` |
|---|---|---|
| Groq (default) | `groq` | `llama3-70b-8192` |
| Anthropic | `anthropic` | `claude-sonnet-4-6` |
| OpenAI | `openai` | `gpt-4o` |

### 4.3 Node Specifications

#### Node 1 — File Ingestion Agent

**File:** `graph/nodes/file_ingestion.py`  
**Type:** Deterministic (no LLM call)  
**Tool:** `tools/excel_parser.py`

**Responsibilities:**
- Accept raw Excel bytes from state
- Parse with `pandas.read_excel()`
- Normalize column names to canonical schema using a configurable column name mapping
- Infer billing period as `{start: min(timestamps), end: max(timestamps)}`
- Surface inferred period to the UI as an advisory notice — the graph proceeds without waiting for user confirmation
- Write `partner_records` and `period` to state

**Canonical schema for partner records:**
```python
{
    "referenceId": str,   # Required — primary match key
    "amount": float,
    "status": str,
    "timestamp": datetime,
    "raw": dict           # Original row preserved for audit
}
```

**Column name mapping (configurable in `config.py`):**
```python
PARTNER_COLUMN_MAP = {
    "reference_id": "referenceId",
    "ref_id": "referenceId",
    "transaction_id": "referenceId",
    "txn_amount": "amount",
    "txn_status": "status",
    "created_at": "timestamp",
}
```

**Validation rules:**
- Raise a descriptive error if `referenceId` column cannot be identified after mapping
- Drop rows where `referenceId` is null/empty and log the count
- Log total rows parsed and any rows skipped

#### Node 2 — DB Query Agent

**File:** `graph/nodes/db_query.py`  
**Type:** Deterministic (no LLM call)  
**Tool:** `tools/mongo_query.py`

**Responsibilities:**
- Read `period` from state
- Query MongoDB transactions collection for all records within `period.start` to `period.end` (inclusive)
- Use cursor-based batch fetching — do not load all records into memory at once
- Normalize MongoDB records to the same canonical schema as partner records
- Write `internal_records` to state

**MongoDB query pattern:**
```python
query = {
    "createdAt": {
        "$gte": period["start"],
        "$lte": period["end"]
    }
}
```

**Required MongoDB index:**
```javascript
db.transactions.createIndex({ createdAt: 1, referenceId: 1 })
```

**Canonical schema for internal records:**
```python
{
    "referenceId": str,
    "amount": float,
    "status": str,
    "timestamp": datetime,
    "raw": dict
}
```

#### Node 3 — Reconciliation Agent

**File:** `graph/nodes/reconciliation.py`  
**Type:** Deterministic (no LLM call)

**Responsibilities:**
Performs a two-pass reconciliation:

**Pass 1 — Set diff on `referenceId`:**
```python
partner_map  = {r["referenceId"]: r for r in state["partner_records"]}
internal_map = {r["referenceId"]: r for r in state["internal_records"]}

partner_ids  = set(partner_map.keys())
internal_ids = set(internal_map.keys())

missing_in_ours    = [partner_map[rid]  for rid in (partner_ids - internal_ids)]
missing_in_partner = [internal_map[rid] for rid in (internal_ids - partner_ids)]
```

**Pass 2 — Field-level comparison on matched records:**
```python
FIELDS_TO_COMPARE = get_fields_to_compare()  # ["amount", "status"] by default

matched = []
for ref_id in partner_ids & internal_ids:
    p = partner_map[ref_id]
    q = internal_map[ref_id]
    diffs = {
        field: {"partner": p.get(field), "ours": q.get(field)}
        for field in FIELDS_TO_COMPARE
        if p.get(field) != q.get(field)
    }
    matched.append(MatchedRecord(
        referenceId=ref_id,
        partner_data=p,
        internal_data=q,
        discrepancies=diffs,
        has_discrepancy=bool(diffs)
    ))
```

**Writes to state:** `missing_in_ours`, `missing_in_partner`, `matched_records`

#### Node 4 — Report Generation Agent

**File:** `graph/nodes/report_generation.py`  
**Type:** LLM-powered  
**LLM:** Via `get_llm()` factory from `config.py`

**Responsibilities:**
- Compute summary statistics from reconciliation results
- Use `with_structured_output(ReconciliationReport)` to guarantee output schema
- Write `report` dict to state

**Output schema:**
```python
class ReconciliationReport(BaseModel):
    period_start: str
    period_end: str
    partner_total: int
    internal_total: int
    matched_total: int
    matched_clean: int             # Matched with no field discrepancies
    matched_flagged: int           # Matched but with at least one field mismatch
    missing_in_ours_count: int
    missing_in_partner_count: int
    match_rate: float              # matched_total / partner_total * 100
    summary_text: str              # 2–4 sentence natural language summary
    flags: list[str]               # Notable observations
```

**Flags logic (deterministic, computed before LLM call):**
- `"Match rate below 95%"` if `match_rate < 95`
- `"Large discrepancy: >1000 records missing in ours"` if `len(missing_in_ours) > 1000`
- `"Large discrepancy: >1000 records missing in partner"` if `len(missing_in_partner) > 1000`
- `"{n} matched transactions have field-level mismatches"` if `matched_flagged > 0`

**LLM prompt guidance:**
Pass only summary statistics and flags to the LLM — never the full record lists. The LLM should act as a financial reconciliation analyst writing a professional summary for the sales team. The summary should call out field-level mismatches specifically where present (e.g. *"14 transactions matched by referenceId but had a status mismatch, suggesting delayed settlement updates on one side."*)

#### Node 5 — Output Dispatcher

**File:** `graph/nodes/dispatcher.py`

Fans out to all registered dispatch branches using LangGraph's `Send` API. In v1.0, only the Excel export branch is active. Email and dashboard branches must exist as stubs that log `"not_implemented"` and return gracefully without raising exceptions.

---

## 5. Output Specifications

### 5.1 Excel Export (v1.0 — Active)

**File:** `dispatch/excel_export.py`  
**Output:** A `.xlsx` file written to `EXPORT_OUTPUT_DIR`, served as a downloadable response.

**Workbook structure (four sheets):**

| Sheet | Contents |
|---|---|
| `Summary` | Period, totals, match rate, matched clean vs flagged counts, flags, narrative summary |
| `Matched` | All transactions found on both sides, with match status and per-field comparison columns |
| `Missing in Ours` | Full records in partner file with no match in internal DB |
| `Missing in Partner` | Full records in internal DB with no match in partner file |

**Matched sheet columns:**

| Column | Description |
|---|---|
| `referenceId` | Shared transaction identifier |
| `amount (ours)` | Amount recorded internally |
| `amount (partner)` | Amount recorded by partner |
| `status (ours)` | Status recorded internally |
| `status (partner)` | Status recorded by partner |
| `match status` | `✓ Clean` or `⚠ {field} mismatch` (e.g. `⚠ status mismatch`, `⚠ amount + status mismatch`) |

**Column order for discrepancy sheets:**  
`referenceId | amount | status | timestamp`

**File naming convention:**  
`reconciliation_{YYYY-MM-DD}_{YYYY-MM-DD}.xlsx`

**Formatting requirements:**
- Header row bold with background fill
- Column widths auto-sized to content
- Timestamp cells formatted as `YYYY-MM-DD HH:MM:SS`
- Amount cells formatted as numeric with 2 decimal places

### 5.2 Email Report (v1.1 — Stub Only)

Implement as a no-op async function. Add a `TODO` comment referencing the full implementation spec. Do not install SendGrid in v1.0 requirements.

### 5.3 Web Dashboard Push (v1.2 — Stub Only)

Implement as a no-op async function that returns state unmodified.

---

## 6. API Specification

### `POST /upload`

**Request:**
```
Content-Type: multipart/form-data
Body: file=<Excel file>
```

**Response (success):**
```json
{
  "status": "success",
  "period": { "start": "2025-01-01", "end": "2025-01-31" },
  "partner_total": 50000,
  "internal_total": 49800,
  "matched_total": 49388,
  "matched_clean": 49374,
  "matched_flagged": 14,
  "missing_in_ours_count": 412,
  "missing_in_partner_count": 189,
  "match_rate": 97.8,
  "summary_text": "...",
  "flags": ["14 matched transactions have field-level mismatches"],
  "download_url": "/exports/reconciliation_2025-01-01_2025-01-31.xlsx",
  "outputs_sent": ["excel"],
  "errors": []
}
```

**Response (pipeline error):**
```json
{
  "status": "error",
  "message": "Could not identify referenceId column in uploaded file.",
  "errors": ["file_ingestion: column mapping failed"]
}
```

### `GET /exports/{filename}`
Serves the generated Excel file for download.

### `GET /health`
Returns `{ "status": "ok", "llm_provider": "groq" }`.

---

## 7. Frontend Requirements

**File:** `frontend/index.html`  
**Type:** Single-page, no framework (plain HTML + Vanilla JS)

### UI States

**Idle** — Drag-and-drop upload zone, upload button (disabled until file selected), LLM provider badge from `GET /health`

**Processing** — Spinner, "Reconciliation in progress…", upload zone disabled

**Results:**
- Advisory notice showing inferred period (non-blocking)
- Summary stats: match rate (large, colour-coded), matched clean vs flagged, missing counts
- Flags displayed as warning badges
- Natural language summary paragraph
- "Download Excel Report" button
- "Run another reconciliation" reset button

**Error** — Error message, specific detail if available, "Try again" button

**Match rate colour coding:** green ≥ 95% · amber 90–95% · red < 90%

---

## 8. LangGraph Graph Wiring

**File:** `graph/graph.py`

```python
from langgraph.graph import StateGraph, END
from langgraph.constants import Send
from graph.state import ReconciliationState
from graph.nodes import (
    file_ingestion, db_query, reconciliation,
    report_generation, dispatcher
)

def build_graph():
    g = StateGraph(ReconciliationState)

    g.add_node("file_ingestion",    file_ingestion.run)
    g.add_node("db_query",          db_query.run)
    g.add_node("reconciliation",    reconciliation.run)
    g.add_node("report_generation", report_generation.run)
    g.add_node("dispatcher",        dispatcher.run)

    g.set_entry_point("file_ingestion")
    g.add_edge("file_ingestion",    "db_query")
    g.add_edge("db_query",          "reconciliation")
    g.add_edge("reconciliation",    "report_generation")
    g.add_edge("report_generation", "dispatcher")
    g.add_edge("dispatcher",        END)

    return g.compile()
```

---

## 9. Error Handling Strategy

| Failure Point | Behaviour |
|---|---|
| Invalid file type (not `.xlsx`) | Reject at API layer before graph starts; return 400 |
| Missing `referenceId` column | Raise in file ingestion node; return error response |
| MongoDB connection failure | Raise in DB query node; return error response |
| MongoDB query timeout | Catch, surface as error response with timeout message |
| LLM API failure (report node) | Fall back to pre-formatted template report without LLM summary; do not abort pipeline |
| Excel export failure | Catch, write to `state["errors"]`; still return partial JSON response |
| Dispatch stub branches | Must never raise — always return state |

---

## 10. Dependencies

```
fastapi
uvicorn[standard]
python-multipart
langgraph
langchain
langchain-groq
langchain-anthropic
langchain-openai
motor
pandas
openpyxl
pydantic
pydantic-settings
python-dotenv
tenacity
```

---

## 11. Testing Requirements

### Unit Tests (required)
- `test_file_ingestion.py` — column mapping normalization, period inference, null referenceId handling
- `test_reconciliation.py` — set operations (all matched, all missing, partial overlap, empty sets) AND field-level comparison (clean match, single field mismatch, multiple field mismatches)

### Fixtures
`tests/fixtures/sample_partner_file.xlsx` — ~20 rows, mix of:
- referenceIds that match MongoDB fixtures (some clean, some with field mismatches)
- referenceIds present only in the partner file
- Non-canonical column headers to test column mapping

### Integration Tests (optional but recommended)
Single end-to-end test using mongomock-motor and a stubbed LLM returning fixed structured output.

---

## 12. Decisions Log

| # | Question | Decision |
|---|---|---|
| 1 | Which fields to compare on matched transactions? | `amount` and `status` only (configurable via `FIELDS_TO_COMPARE`) |
| 2 | Should the inferred period be a blocking confirmation or advisory? | Advisory — graph proceeds without waiting for user confirmation |
| 3 | Pre-signed URL for large email attachments? | Not required — always attach workbook directly |
| 4 | Should flagged matched records trigger automated follow-up? | No — reporting is sufficient |

---

## 13. Implementation Notes for Claude Code

1. **Start with `config.py` and `graph/state.py`** — define `MatchedRecord` and `ReconciliationState` here before touching any node.

2. **Implement nodes in pipeline order** — ingestion → DB query → reconciliation → report → dispatcher. Test each in isolation before wiring the graph.

3. **The reconciliation node must be purely deterministic** — no LLM, no external calls. Both passes (set diff and field-level comparison) are covered by unit tests.

4. **Use `with_structured_output(ReconciliationReport)` in the report node** — do not parse LLM text output manually.

5. **Do not pass full record lists to the LLM** — pass only counts, match rate, and flags. At 50K records this will exceed context windows and incur unnecessary token costs.

6. **The dispatcher stub branches must not raise exceptions** — write to `state["errors"]` and return.

7. **Serve the frontend from FastAPI** using `StaticFiles` or a single route — no separate frontend server needed.

8. **All async** — use `async def` throughout, `motor` for MongoDB, and `await graph.ainvoke()`.
