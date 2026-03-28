import logging

logger = logging.getLogger(__name__)


async def push(state: dict) -> str:
    """Stub for dashboard push. TODO: Implement web dashboard push in v1.2."""
    logger.info("Dashboard push: not implemented (v1.2 stub)")
    return "dashboard_stub"
