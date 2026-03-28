# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VAS (Value Added Services) transaction reconciliation system. A LangGraph multi-agent pipeline that accepts a partner Excel file, queries MongoDB for internal records, performs two-pass reconciliation on `referenceId`, generates an LLM-powered report, and exports results as Excel. Full spec in `recon_prd_full.md`.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn main:app --reload

# Run tests
pytest tests/

# Run a single test file
pytest tests/test_reconciliation.py -v
```

## Architecture

**Pipeline flow:** FastAPI endpoint → LangGraph StateGraph → 5 sequential nodes → response

```
POST /upload → file_ingestion → db_query → reconciliation → report_generation → dispatcher → END
```

All nodes share a single `ReconciliationState` TypedDict (defined in `graph/state.py`). Each node reads from and writes to specific keys in this state.

**Key architectural rules:**
- Nodes 1-3 (ingestion, db_query, reconciliation) are deterministic — no LLM calls
- Node 4 (report_generation) is the only LLM-powered node; receives only summary stats, never full record lists; falls back to template on LLM failure
- Node 5 (dispatcher) fans out to dispatch branches; only Excel export is active in v1.0, email/dashboard are stubs
- Everything is async (`async def`, `motor` for MongoDB, `await graph.ainvoke()`)

**LLM provider switching:** Controlled via `LLM_PROVIDER` env var in `config.py`. Supports groq (default), anthropic, openai.

**Reconciliation logic (Node 3):**
- Pass 1: Set diff on `referenceId` to find missing transactions on either side
- Pass 2: Field-level comparison on matched records for configurable fields (`FIELDS_TO_COMPARE`)

**Error handling:** LLM failure falls back to template report (3 retries with exponential backoff first). Dispatch stubs must never raise. File/DB errors surface as error responses.

**Important patterns:**
- LLM provider imports are lazy (inside `get_llm()` and `_invoke_llm()`) to avoid requiring all provider packages at import time
- `outputs_sent` and `errors` in state use `Annotated[list, operator.add]` reducers so values accumulate across nodes
- Motor client is a singleton managed via FastAPI lifespan (startup/shutdown)
- `uploaded_file` bytes are cleared from state after ingestion to save memory
