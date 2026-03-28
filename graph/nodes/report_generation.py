import logging

from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

from config import get_llm
from graph.state import ReconciliationState, ReconciliationReport

logger = logging.getLogger(__name__)


async def run(state: ReconciliationState) -> dict:
    """Generate reconciliation report. LLM produces summary text; stats are deterministic."""
    # Compute deterministic stats
    partner_total = len(state["partner_records"])
    internal_total = len(state["internal_records"])
    matched_records = state["matched_records"]
    matched_total = len(matched_records)
    matched_flagged = sum(1 for m in matched_records if m["has_discrepancy"])
    matched_clean = matched_total - matched_flagged
    missing_in_ours_count = len(state["missing_in_ours"])
    missing_in_partner_count = len(state["missing_in_partner"])
    match_rate = (matched_total / partner_total * 100) if partner_total > 0 else 0.0

    period = state["period"]
    period_start = period["start"].strftime("%Y-%m-%d") if period.get("start") else "unknown"
    period_end = period["end"].strftime("%Y-%m-%d") if period.get("end") else "unknown"

    # Compute flags
    flags = []
    if match_rate < 95:
        flags.append("Match rate below 95%")
    if missing_in_ours_count > 1000:
        flags.append(f"Large discrepancy: >{missing_in_ours_count} records missing in ours")
    if missing_in_partner_count > 1000:
        flags.append(f"Large discrepancy: >{missing_in_partner_count} records missing in partner")
    if matched_flagged > 0:
        flags.append(f"{matched_flagged} matched transactions have field-level mismatches")

    # Build base report (everything except summary_text)
    base = {
        "period_start": period_start,
        "period_end": period_end,
        "partner_total": partner_total,
        "internal_total": internal_total,
        "matched_total": matched_total,
        "matched_clean": matched_clean,
        "matched_flagged": matched_flagged,
        "missing_in_ours_count": missing_in_ours_count,
        "missing_in_partner_count": missing_in_partner_count,
        "match_rate": round(match_rate, 2),
        "flags": flags,
    }

    # Try LLM for summary text, fall back to template on failure
    summary_text = _generate_summary_llm(base)
    if summary_text is None:
        summary_text = _template_summary(base)

    report = ReconciliationReport(**base, summary_text=summary_text)
    logger.info(f"Report generation complete: match_rate={report.match_rate}%, flags={report.flags}")
    return {"report": report.model_dump()}


def _generate_summary_llm(stats: dict) -> str | None:
    """Attempt to generate a natural language summary via LLM. Returns None on failure."""
    try:
        return _invoke_llm(stats)
    except Exception as e:
        logger.error(f"LLM summary generation failed, falling back to template: {e}")
        return None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def _invoke_llm(stats: dict) -> str:
    """Call the LLM with structured output to get a summary. Retries on transient failures."""
    from langchain_core.messages import SystemMessage, HumanMessage

    llm = get_llm()

    system_prompt = (
        "You are a financial reconciliation analyst writing a professional summary for the sales team. "
        "Write a concise 2-4 sentence summary of the reconciliation results. "
        "Call out field-level mismatches specifically where present. "
        "Be factual and precise."
    )

    stats_text = "\n".join(f"- {k}: {v}" for k, v in stats.items())
    human_prompt = f"Reconciliation statistics:\n{stats_text}\n\nWrite the summary."

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt),
    ])

    return response.content.strip()


def _template_summary(stats: dict) -> str:
    """Fallback template summary when LLM is unavailable."""
    return (
        f"Reconciliation for period {stats['period_start']} to {stats['period_end']} completed. "
        f"Of {stats['partner_total']} partner records, {stats['matched_total']} matched "
        f"({stats['match_rate']}% match rate). "
        f"{stats['matched_clean']} matched cleanly, {stats['matched_flagged']} had field-level discrepancies. "
        f"{stats['missing_in_ours_count']} records missing in our system, "
        f"{stats['missing_in_partner_count']} missing in partner file."
    )
