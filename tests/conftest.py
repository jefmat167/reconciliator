import io
from datetime import datetime

import openpyxl
import pytest


@pytest.fixture
def sample_partner_bytes():
    """Generate a sample partner Excel file as bytes.

    Contains 20 rows with non-canonical column headers to test mapping.
    Mix of:
    - referenceIds that will match internal records (some clean, some with mismatches)
    - referenceIds only in partner file
    - One row with empty referenceId (should be dropped)
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["reference_id", "txn_amount", "txn_status", "created_at"])

    rows = [
        ("REF001", 100.00, "success", datetime(2025, 1, 5, 10, 0)),
        ("REF002", 200.00, "success", datetime(2025, 1, 6, 11, 0)),
        ("REF003", 300.00, "success", datetime(2025, 1, 7, 12, 0)),
        ("REF004", 400.00, "pending", datetime(2025, 1, 8, 13, 0)),
        ("REF005", 500.00, "success", datetime(2025, 1, 9, 14, 0)),
        ("REF006", 150.50, "success", datetime(2025, 1, 10, 9, 0)),
        ("REF007", 250.75, "failed", datetime(2025, 1, 11, 10, 30)),
        ("REF008", 350.00, "success", datetime(2025, 1, 12, 11, 0)),
        ("REF009", 450.25, "success", datetime(2025, 1, 13, 12, 0)),
        ("REF010", 550.00, "pending", datetime(2025, 1, 14, 13, 0)),
        # Amount mismatch on REF011
        ("REF011", 999.99, "success", datetime(2025, 1, 15, 14, 0)),
        # Status mismatch on REF012
        ("REF012", 120.00, "success", datetime(2025, 1, 16, 15, 0)),
        # Both amount + status mismatch on REF013
        ("REF013", 888.00, "failed", datetime(2025, 1, 17, 16, 0)),
        ("REF014", 140.00, "success", datetime(2025, 1, 18, 17, 0)),
        ("REF015", 160.00, "success", datetime(2025, 1, 19, 8, 0)),
        # Partner-only records (no match in internal)
        ("REF016", 170.00, "success", datetime(2025, 1, 20, 9, 0)),
        ("REF017", 180.00, "pending", datetime(2025, 1, 21, 10, 0)),
        ("REF018", 190.00, "success", datetime(2025, 1, 22, 11, 0)),
        # Clean match
        ("REF019", 200.00, "success", datetime(2025, 1, 23, 12, 0)),
        # Empty referenceId — should be dropped
        ("", 999.00, "success", datetime(2025, 1, 24, 13, 0)),
    ]
    for row in rows:
        ws.append(row)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture
def sample_partner_records():
    """Pre-parsed partner records in canonical schema (matching the Excel above)."""
    return [
        {"referenceId": f"REF{str(i).zfill(3)}", "amount": amt, "status": st, "timestamp": ts, "raw": {}}
        for i, (amt, st, ts) in enumerate([
            (100.00, "success", datetime(2025, 1, 5, 10, 0)),
            (200.00, "success", datetime(2025, 1, 6, 11, 0)),
            (300.00, "success", datetime(2025, 1, 7, 12, 0)),
            (400.00, "pending", datetime(2025, 1, 8, 13, 0)),
            (500.00, "success", datetime(2025, 1, 9, 14, 0)),
        ], start=1)
    ]


@pytest.fixture
def sample_internal_records():
    """Internal records with some mismatches and some missing from partner.

    REF001-REF005: clean matches with sample_partner_records
    REF006: internal-only (missing in partner for this fixture)
    """
    records = [
        {"referenceId": f"REF{str(i).zfill(3)}", "amount": amt, "status": st, "timestamp": ts, "raw": {}}
        for i, (amt, st, ts) in enumerate([
            (100.00, "success", datetime(2025, 1, 5, 10, 0)),
            (200.00, "success", datetime(2025, 1, 6, 11, 0)),
            (300.00, "success", datetime(2025, 1, 7, 12, 0)),
            (400.00, "pending", datetime(2025, 1, 8, 13, 0)),
            (500.00, "success", datetime(2025, 1, 9, 14, 0)),
        ], start=1)
    ]
    # Internal-only record
    records.append({
        "referenceId": "REF006",
        "amount": 150.50,
        "status": "success",
        "timestamp": datetime(2025, 1, 10, 9, 0),
        "raw": {},
    })
    return records


@pytest.fixture
def full_internal_records():
    """Internal records matching the full 20-row partner file fixture.

    REF001-REF015, REF019: present in internal (some with mismatches)
    REF016-REF018: absent from internal (partner-only)
    REF020: internal-only (absent from partner)
    """
    base = [
        ("REF001", 100.00, "success", datetime(2025, 1, 5, 10, 0)),
        ("REF002", 200.00, "success", datetime(2025, 1, 6, 11, 0)),
        ("REF003", 300.00, "success", datetime(2025, 1, 7, 12, 0)),
        ("REF004", 400.00, "pending", datetime(2025, 1, 8, 13, 0)),
        ("REF005", 500.00, "success", datetime(2025, 1, 9, 14, 0)),
        ("REF006", 150.50, "success", datetime(2025, 1, 10, 9, 0)),
        ("REF007", 250.75, "failed", datetime(2025, 1, 11, 10, 30)),
        ("REF008", 350.00, "success", datetime(2025, 1, 12, 11, 0)),
        ("REF009", 450.25, "success", datetime(2025, 1, 13, 12, 0)),
        ("REF010", 550.00, "pending", datetime(2025, 1, 14, 13, 0)),
        # Amount mismatch: partner has 999.99, internal has 600.00
        ("REF011", 600.00, "success", datetime(2025, 1, 15, 14, 0)),
        # Status mismatch: partner has "success", internal has "pending"
        ("REF012", 120.00, "pending", datetime(2025, 1, 16, 15, 0)),
        # Both mismatches: partner has (888.00, "failed"), internal has (300.00, "success")
        ("REF013", 300.00, "success", datetime(2025, 1, 17, 16, 0)),
        ("REF014", 140.00, "success", datetime(2025, 1, 18, 17, 0)),
        ("REF015", 160.00, "success", datetime(2025, 1, 19, 8, 0)),
        # REF016-REF018 intentionally absent (partner-only)
        ("REF019", 200.00, "success", datetime(2025, 1, 23, 12, 0)),
        # Internal-only record
        ("REF020", 210.00, "success", datetime(2025, 1, 25, 14, 0)),
    ]
    return [
        {"referenceId": rid, "amount": amt, "status": st, "timestamp": ts, "raw": {}}
        for rid, amt, st, ts in base
    ]
