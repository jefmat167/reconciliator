import asyncio
import logging

from graph.state import ReconciliationState
from tools import mongo_query

logger = logging.getLogger(__name__)

QUERY_TIMEOUT_SECONDS = 120


async def run(state: ReconciliationState) -> dict:
    """Query MongoDB for internal records covering the inferred period and partner."""
    period = state["period"]
    partner = state["partner"]
    logger.info(f"DB query: fetching records for partner={partner}, period {period['start']} to {period['end']}")

    try:
        records = await asyncio.wait_for(
            mongo_query.fetch_records(period, partner),
            timeout=QUERY_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise TimeoutError(
            f"MongoDB query timed out after {QUERY_TIMEOUT_SECONDS}s "
            f"for period {period['start']} to {period['end']}"
        )

    logger.info(f"DB query: complete — {len(records)} internal records fetched")
    return {"internal_records": records}
