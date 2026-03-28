import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from graph.graph import build_graph
from tools.mongo_query import get_client, close_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

graph = None


def _validate_settings():
    """Fail fast on missing critical configuration."""
    if not settings.mongodb_uri:
        raise RuntimeError("MONGODB_URI is required")
    if not settings.mongodb_db:
        raise RuntimeError("MONGODB_DB is required")
    if not settings.mongodb_collection:
        raise RuntimeError("MONGODB_COLLECTION is required")
    logger.info(
        f"Config validated: llm_provider={settings.llm_provider}, "
        f"db={settings.mongodb_db}.{settings.mongodb_collection}"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph
    _validate_settings()
    os.makedirs(settings.export_output_dir, exist_ok=True)
    get_client()  # Initialize motor client
    graph = build_graph()
    logger.info("App started: graph compiled, motor client ready")
    yield
    close_client()
    logger.info("App shutdown: motor client closed")


app = FastAPI(title="VAS Reconciliation System", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "llm_provider": settings.llm_provider}


VALID_PARTNERS = {"xpresspay", "easyPay"}


@app.post("/upload")
async def upload(file: UploadFile, partner: str = Form(...)):
    # Validate partner
    if partner not in VALID_PARTNERS:
        raise HTTPException(status_code=400, detail=f"Invalid partner. Must be one of: {', '.join(VALID_PARTNERS)}")

    # Validate file type
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx files are accepted")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    initial_state = {
        "uploaded_file": file_bytes,
        "partner": partner,
        "period": {},
        "partner_records": [],
        "internal_records": [],
        "missing_in_ours": [],
        "missing_in_partner": [],
        "matched_records": [],
        "report": {},
        "outputs_sent": [],
        "errors": [],
    }

    try:
        result = await graph.ainvoke(initial_state)
    except ValueError as e:
        # Validation errors from file ingestion (e.g. missing referenceId column)
        return {"status": "error", "message": str(e), "errors": [f"file_ingestion: {e}"]}
    except TimeoutError as e:
        return {"status": "error", "message": str(e), "errors": [f"db_query: {e}"]}
    except Exception as e:
        logger.exception("Pipeline failed with unexpected error")
        return {"status": "error", "message": "An unexpected error occurred", "errors": [str(e)]}

    report = result.get("report", {})
    period = result.get("period", {})

    start_str = period["start"].strftime("%Y-%m-%d") if period.get("start") else "unknown"
    end_str = period["end"].strftime("%Y-%m-%d") if period.get("end") else "unknown"
    filename = f"reconciliation_{start_str}_{end_str}.xlsx"

    return {
        "status": "success",
        "period": {"start": start_str, "end": end_str},
        "partner_total": report.get("partner_total"),
        "internal_total": report.get("internal_total"),
        "matched_total": report.get("matched_total"),
        "matched_clean": report.get("matched_clean"),
        "matched_flagged": report.get("matched_flagged"),
        "missing_in_ours_count": report.get("missing_in_ours_count"),
        "missing_in_partner_count": report.get("missing_in_partner_count"),
        "match_rate": report.get("match_rate"),
        "summary_text": report.get("summary_text"),
        "flags": report.get("flags", []),
        "download_url": f"/exports/{filename}",
        "outputs_sent": result.get("outputs_sent", []),
        "errors": result.get("errors", []),
    }


@app.get("/exports/{filename}")
async def download_export(filename: str):
    # Prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    filepath = os.path.join(settings.export_output_dir, filename)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "index.html")
    with open(frontend_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
