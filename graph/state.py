import operator
from typing import Annotated, TypedDict
from datetime import datetime

from pydantic import BaseModel


class MatchedRecord(BaseModel):
    referenceId: str
    partner_data: dict
    internal_data: dict
    discrepancies: dict  # {field: {"partner": val, "ours": val}}
    has_discrepancy: bool


class ReconciliationReport(BaseModel):
    period_start: str
    period_end: str
    partner_total: int
    internal_total: int
    matched_total: int
    matched_clean: int
    matched_flagged: int
    missing_in_ours_count: int
    missing_in_partner_count: int
    match_rate: float
    summary_text: str
    flags: list[str]


class ReconciliationState(TypedDict):
    uploaded_file: bytes
    partner: str  # Service provider name (e.g. "xpresspay", "easyPay")
    period: dict  # {"start": datetime, "end": datetime}
    partner_records: list[dict]
    internal_records: list[dict]
    missing_in_ours: list[dict]
    missing_in_partner: list[dict]
    matched_records: list[dict]  # list of MatchedRecord.model_dump() dicts
    report: dict
    outputs_sent: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]
