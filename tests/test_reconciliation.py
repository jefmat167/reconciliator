import pytest
import asyncio
from datetime import datetime

from graph.nodes.reconciliation import run as reconcile


def _make_state(partner_records, internal_records):
    """Build a minimal ReconciliationState dict for the reconciliation node."""
    return {
        "partner_records": partner_records,
        "internal_records": internal_records,
    }


def _run(state):
    """Run the async reconciliation node synchronously."""
    return asyncio.new_event_loop().run_until_complete(reconcile(state))


class TestPass1SetDiff:
    """Test set-based diff on referenceId."""

    def test_all_matched(self):
        """When both sides have identical referenceIds, no missing records."""
        partner = [{"referenceId": "A", "amount": 1, "status": "ok", "raw": {}}]
        internal = [{"referenceId": "A", "amount": 1, "status": "ok", "raw": {}}]
        result = _run(_make_state(partner, internal))

        assert result["missing_in_ours"] == []
        assert result["missing_in_partner"] == []
        assert len(result["matched_records"]) == 1

    def test_all_missing_in_ours(self):
        """Partner has records, internal has none."""
        partner = [
            {"referenceId": "A", "amount": 1, "status": "ok", "raw": {}},
            {"referenceId": "B", "amount": 2, "status": "ok", "raw": {}},
        ]
        result = _run(_make_state(partner, []))

        assert len(result["missing_in_ours"]) == 2
        assert result["missing_in_partner"] == []
        assert result["matched_records"] == []

    def test_all_missing_in_partner(self):
        """Internal has records, partner has none."""
        internal = [
            {"referenceId": "X", "amount": 1, "status": "ok", "raw": {}},
        ]
        result = _run(_make_state([], internal))

        assert result["missing_in_ours"] == []
        assert len(result["missing_in_partner"]) == 1
        assert result["matched_records"] == []

    def test_partial_overlap(self, sample_partner_records, sample_internal_records):
        """REF001-REF005 overlap, REF006 internal-only."""
        result = _run(_make_state(sample_partner_records, sample_internal_records))

        assert len(result["matched_records"]) == 5
        assert len(result["missing_in_ours"]) == 0
        assert len(result["missing_in_partner"]) == 1
        assert result["missing_in_partner"][0]["referenceId"] == "REF006"

    def test_empty_both_sides(self):
        """No records on either side."""
        result = _run(_make_state([], []))

        assert result["missing_in_ours"] == []
        assert result["missing_in_partner"] == []
        assert result["matched_records"] == []

    def test_full_scenario(self, full_internal_records, sample_partner_bytes):
        """Full 20-row partner file against internal records.

        Partner: REF001-REF019 (REF with empty id dropped)
        Internal: REF001-REF015, REF019, REF020
        Missing in ours: REF016, REF017, REF018
        Missing in partner: REF020
        """
        from tools.excel_parser import parse
        partner_records, _, _ = parse(sample_partner_bytes)

        result = _run(_make_state(partner_records, full_internal_records))

        missing_in_ours_ids = {r["referenceId"] for r in result["missing_in_ours"]}
        missing_in_partner_ids = {r["referenceId"] for r in result["missing_in_partner"]}

        assert missing_in_ours_ids == {"REF016", "REF017", "REF018"}
        assert missing_in_partner_ids == {"REF020"}
        assert len(result["matched_records"]) == 16


class TestPass2FieldComparison:
    """Test field-level comparison on matched records."""

    def test_clean_match(self):
        """Identical values on compared fields — no discrepancies."""
        partner = [{"referenceId": "A", "amount": 100.0, "status": "success", "raw": {}}]
        internal = [{"referenceId": "A", "amount": 100.0, "status": "success", "raw": {}}]
        result = _run(_make_state(partner, internal))

        matched = result["matched_records"][0]
        assert matched["has_discrepancy"] is False
        assert matched["discrepancies"] == {}

    def test_amount_mismatch(self):
        """Different amount values flagged as discrepancy."""
        partner = [{"referenceId": "A", "amount": 100.0, "status": "success", "raw": {}}]
        internal = [{"referenceId": "A", "amount": 200.0, "status": "success", "raw": {}}]
        result = _run(_make_state(partner, internal))

        matched = result["matched_records"][0]
        assert matched["has_discrepancy"] is True
        assert "amount" in matched["discrepancies"]
        assert matched["discrepancies"]["amount"]["partner"] == 100.0
        assert matched["discrepancies"]["amount"]["ours"] == 200.0

    def test_status_mismatch(self):
        """Different status values flagged as discrepancy."""
        partner = [{"referenceId": "A", "amount": 100.0, "status": "success", "raw": {}}]
        internal = [{"referenceId": "A", "amount": 100.0, "status": "pending", "raw": {}}]
        result = _run(_make_state(partner, internal))

        matched = result["matched_records"][0]
        assert matched["has_discrepancy"] is True
        assert "status" in matched["discrepancies"]
        assert matched["discrepancies"]["status"]["partner"] == "success"
        assert matched["discrepancies"]["status"]["ours"] == "pending"

    def test_multiple_field_mismatches(self):
        """Both amount and status differ."""
        partner = [{"referenceId": "A", "amount": 100.0, "status": "success", "raw": {}}]
        internal = [{"referenceId": "A", "amount": 999.0, "status": "failed", "raw": {}}]
        result = _run(_make_state(partner, internal))

        matched = result["matched_records"][0]
        assert matched["has_discrepancy"] is True
        assert "amount" in matched["discrepancies"]
        assert "status" in matched["discrepancies"]

    def test_no_matched_records_skips_pass2(self):
        """When there are no matched records, pass 2 produces nothing."""
        partner = [{"referenceId": "A", "amount": 1, "status": "ok", "raw": {}}]
        internal = [{"referenceId": "B", "amount": 2, "status": "ok", "raw": {}}]
        result = _run(_make_state(partner, internal))

        assert result["matched_records"] == []

    def test_full_scenario_discrepancies(self, full_internal_records, sample_partner_bytes):
        """REF011: amount mismatch, REF012: status mismatch, REF013: both."""
        from tools.excel_parser import parse
        partner_records, _, _ = parse(sample_partner_bytes)

        result = _run(_make_state(partner_records, full_internal_records))

        flagged = {m["referenceId"]: m for m in result["matched_records"] if m["has_discrepancy"]}

        assert "REF011" in flagged
        assert "amount" in flagged["REF011"]["discrepancies"]
        assert "status" not in flagged["REF011"]["discrepancies"]

        assert "REF012" in flagged
        assert "status" in flagged["REF012"]["discrepancies"]
        assert "amount" not in flagged["REF012"]["discrepancies"]

        assert "REF013" in flagged
        assert "amount" in flagged["REF013"]["discrepancies"]
        assert "status" in flagged["REF013"]["discrepancies"]

        clean = [m for m in result["matched_records"] if not m["has_discrepancy"]]
        assert len(clean) == 13  # 16 matched - 3 flagged
