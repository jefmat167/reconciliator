import logging

logger = logging.getLogger(__name__)


async def send(state: dict) -> str:
    """Stub for email dispatch. TODO: Implement via SendGrid or SMTP in v1.1."""
    logger.info("Email dispatch: not implemented (v1.1 stub)")
    return "email_stub"
