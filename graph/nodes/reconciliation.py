import logging

from config import get_fields_to_compare
from graph.state import ReconciliationState, MatchedRecord

logger = logging.getLogger(__name__)


async def run(state: ReconciliationState) -> dict:
    """Two-pass deterministic reconciliation. No LLM, no external calls."""
    partner_records = state["partner_records"]
    internal_records = state["internal_records"]
    fields_to_compare = get_fields_to_compare()

    # Build lookup maps — warn on duplicate referenceIds
    partner_map = _build_map(partner_records, "partner")
    internal_map = _build_map(internal_records, "internal")

    partner_ids = set(partner_map.keys())
    internal_ids = set(internal_map.keys())

    # Pass 1: Set diff on referenceId
    missing_in_ours = [partner_map[rid] for rid in sorted(partner_ids - internal_ids)]
    missing_in_partner = [internal_map[rid] for rid in sorted(internal_ids - partner_ids)]

    # Pass 2: Field-level comparison on matched records
    matched_ids = partner_ids & internal_ids
    matched_records = []
    for ref_id in sorted(matched_ids):
        p = partner_map[ref_id]
        q = internal_map[ref_id]
        diffs = {}
        for field in fields_to_compare:
            p_val = p.get(field)
            q_val = q.get(field)
            if p_val != q_val:
                diffs[field] = {"partner": p_val, "ours": q_val}
        record = MatchedRecord(
            referenceId=ref_id,
            partner_data=p,
            internal_data=q,
            discrepancies=diffs,
            has_discrepancy=bool(diffs),
        )
        matched_records.append(record.model_dump())

    logger.info(
        f"Reconciliation complete: {len(matched_records)} matched "
        f"({sum(1 for m in matched_records if m['has_discrepancy'])} with discrepancies), "
        f"{len(missing_in_ours)} missing in ours, "
        f"{len(missing_in_partner)} missing in partner"
    )

    return {
        "missing_in_ours": missing_in_ours,
        "missing_in_partner": missing_in_partner,
        "matched_records": matched_records,
    }


def _build_map(records: list[dict], label: str) -> dict[str, dict]:
    """Build a referenceId -> record map, logging duplicates."""
    seen: dict[str, dict] = {}
    dup_count = 0
    for r in records:
        rid = r.get("referenceId")
        if rid in seen:
            dup_count += 1
        seen[rid] = r  # Last occurrence wins
    if dup_count > 0:
        logger.warning(f"Found {dup_count} duplicate referenceIds in {label} records (last occurrence kept)")
    return seen
