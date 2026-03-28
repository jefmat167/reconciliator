# VAS Reconciliation System

Automated end-of-month transaction reconciliation between VAS partner records and internal MongoDB data. Upload a partner's Excel file, select the partner, and get a full reconciliation report in seconds.

## What It Does

1. **Upload** a partner Excel file (`.xlsx`) via the web UI
2. **Select** the partner (xpresspay or easyPay)
3. **Automatic period inference** from the file's date column
4. **Two-pass reconciliation** against internal MongoDB records:
   - **Pass 1:** Set diff on transaction reference to find missing records on either side
   - **Pass 2:** Field-level comparison (amount, status) on matched records to surface mismatches
5. **LLM-generated summary** of reconciliation results
6. **Download** a four-sheet Excel report (Summary, Matched, Missing in Ours, Missing in Partner)

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI |
| Agent orchestration | LangGraph (StateGraph) |
| LLM | LangChain (Groq / Anthropic / OpenAI — switchable) |
| Database | MongoDB via Motor (async) |
| Excel parsing | pandas + openpyxl |
| Frontend | Plain HTML + Vanilla JS |

## Setup

### 1. Clone and install

```bash
git clone <repo-url>
cd reconciliator
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile
GROQ_API_KEY=your_key_here

MONGODB_URI=your_mongodb_connection_string
MONGODB_DB=your_database_name
MONGODB_COLLECTION=collection_name

EXPORT_OUTPUT_DIR=./exports
FIELDS_TO_COMPARE=amount,status
```

### 3. Run

```bash
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000` in your browser.

## Project Structure

```
├── main.py                     # FastAPI app, endpoints, startup
├── config.py                   # Settings, LLM factory, column mapping
├── graph/
│   ├── state.py                # ReconciliationState, MatchedRecord, ReconciliationReport
│   ├── graph.py                # LangGraph StateGraph wiring
│   └── nodes/
│       ├── file_ingestion.py   # Excel parsing and period inference
│       ├── db_query.py         # MongoDB query with timeout
│       ├── reconciliation.py   # Two-pass deterministic reconciliation
│       ├── report_generation.py# LLM summary with template fallback
│       └── dispatcher.py       # Fan-out to dispatch branches
├── dispatch/
│   ├── excel_export.py         # Four-sheet Excel report generation
│   ├── email_report.py         # Stub (v1.1)
│   └── dashboard_push.py       # Stub (v1.2)
├── tools/
│   ├── excel_parser.py         # pandas parsing, column normalization
│   └── mongo_query.py          # Motor async queries with projection
├── frontend/
│   └── index.html              # Single-page upload and results UI
└── tests/
    ├── conftest.py             # Shared fixtures
    ├── test_file_ingestion.py  # 14 tests
    └── test_reconciliation.py  # 12 tests
```

## Pipeline

```
POST /upload
  → file_ingestion (parse Excel, infer period)
  → db_query (fetch internal records from MongoDB)
  → reconciliation (set diff + field comparison)
  → report_generation (deterministic stats + LLM summary)
  → dispatcher (Excel export + stubs)
  → JSON response + downloadable .xlsx
```

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Web UI |
| `GET` | `/health` | Status and LLM provider |
| `POST` | `/upload` | Upload Excel file + partner name, run reconciliation |
| `GET` | `/exports/{filename}` | Download generated report |

## Tests

```bash
pytest tests/ -v
```

26 tests covering file ingestion (column mapping, period inference, validation) and reconciliation logic (set diff, field comparison, edge cases).

## LLM Provider Switching

Change `LLM_PROVIDER` and `LLM_MODEL` in `.env`:

| Provider | `LLM_PROVIDER` | `LLM_MODEL` |
|---|---|---|
| Groq (default) | `groq` | `llama-3.3-70b-versatile` |
| Anthropic | `anthropic` | `claude-sonnet-4-6` |
| OpenAI | `openai` | `gpt-4o` |

If the LLM call fails, the report falls back to a template summary — the pipeline never breaks.

## Roadmap

- **v1.1** — Email dispatch (SendGrid/SMTP)
- **v1.2** — Interactive web dashboard with trend charts and drill-down views
