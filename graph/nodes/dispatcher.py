import asyncio
import logging

from graph.state import ReconciliationState
from dispatch import excel_export, email_report, dashboard_push

logger = logging.getLogger(__name__)


async def run(state: ReconciliationState) -> dict:
    """Fan out to all dispatch branches. Collects results and errors."""
    logger.info("Dispatcher: starting dispatch branches")

    branches = [
        ("excel", excel_export.export),
        ("email", email_report.send),
        ("dashboard", dashboard_push.push),
    ]

    tasks = [branch_fn(state) for _, branch_fn in branches]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    outputs_sent = []
    errors = []
    for (name, _), result in zip(branches, results):
        if isinstance(result, Exception):
            msg = f"{name}: {result}"
            logger.error(f"Dispatcher: branch '{name}' failed — {result}")
            errors.append(msg)
        elif isinstance(result, str):
            outputs_sent.append(result)

    logger.info(f"Dispatcher: complete — sent={outputs_sent}, errors={errors}")
    return {"outputs_sent": outputs_sent, "errors": errors}
