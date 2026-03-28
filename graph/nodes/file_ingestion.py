import logging

from graph.state import ReconciliationState
from tools import excel_parser

logger = logging.getLogger(__name__)


async def run(state: ReconciliationState) -> dict:
    """Parse uploaded Excel file, extract partner records and inferred period."""
    logger.info("File ingestion: starting")

    records, period, metadata = excel_parser.parse(state["uploaded_file"])

    logger.info(
        f"File ingestion: complete — {metadata['total_rows']} records, "
        f"{metadata['dropped_rows']} dropped, period {period['start']} to {period['end']}"
    )

    return {
        "partner_records": records,
        "period": period,
        "uploaded_file": b"",  # Clear bytes from state to save memory
    }
