import io
import logging
from datetime import datetime

import pandas as pd

from config import PARTNER_COLUMN_MAP

logger = logging.getLogger(__name__)


def parse(file_bytes: bytes) -> tuple[list[dict], dict, dict]:
    """Parse partner Excel file and return (records, period, metadata).

    Returns:
        records: List of dicts in canonical schema.
        period: {"start": datetime, "end": datetime} inferred from timestamps.
        metadata: {"total_rows": int, "dropped_rows": int}
    """
    df = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
    original_count = len(df)
    logger.info(f"Parsed Excel file: {original_count} rows, columns: {list(df.columns)}")

    # Normalize column names via mapping (case-insensitive)
    col_rename = {}
    for col in df.columns:
        key = col.strip().lower().replace(" ", "_")
        if key in PARTNER_COLUMN_MAP:
            col_rename[col] = PARTNER_COLUMN_MAP[key]
    df = df.rename(columns=col_rename)

    if "referenceId" not in df.columns:
        raise ValueError(
            f"Could not identify referenceId column in uploaded file. "
            f"Columns after mapping: {list(df.columns)}. "
            f"Expected one of: {[k for k, v in PARTNER_COLUMN_MAP.items() if v == 'referenceId']}"
        )

    # Drop rows with null/empty referenceId
    mask = df["referenceId"].isna() | (df["referenceId"].astype(str).str.strip() == "")
    dropped_count = int(mask.sum())
    if dropped_count > 0:
        logger.warning(f"Dropping {dropped_count} rows with null/empty referenceId")
        df = df[~mask].copy()

    # Convert referenceId to string
    df["referenceId"] = df["referenceId"].astype(str).str.strip()

    # Parse timestamp column if present
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # Build canonical records
    canonical_fields = {"referenceId", "amount", "status", "timestamp"}
    records = []
    for _, row in df.iterrows():
        raw = row.to_dict()
        record = {}
        for field in canonical_fields:
            if field in row.index:
                val = row[field]
                # Convert pandas types to native Python types
                if pd.isna(val):
                    record[field] = None
                elif isinstance(val, pd.Timestamp):
                    record[field] = val.to_pydatetime()
                else:
                    record[field] = val
            else:
                record[field] = None
        # Sanitize raw dict for JSON serialization
        record["raw"] = {
            k: (v.isoformat() if isinstance(v, (datetime, pd.Timestamp)) else v)
            for k, v in raw.items()
            if not pd.isna(v)
        }
        records.append(record)

    # Infer period from timestamp range
    period = {"start": None, "end": None}
    if "timestamp" in df.columns:
        valid_ts = df["timestamp"].dropna()
        if not valid_ts.empty:
            period["start"] = valid_ts.min().to_pydatetime()
            period["end"] = valid_ts.max().to_pydatetime()

    metadata = {"total_rows": len(records), "dropped_rows": dropped_count}
    logger.info(f"Parsed {metadata['total_rows']} records, dropped {dropped_count}, period: {period}")
    return records, period, metadata
