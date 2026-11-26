"""Cleaning pipeline: each step is small, pure and logged.

Every step returns the cleaned frame and a short audit line, so the run
produces a record of exactly what was changed and how many rows it touched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from .generate import PAYER_VARIANTS

# Canonical payer lookup built from known variants (normalised keys)
def _norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


PAYER_LOOKUP = {_norm(v): canon for canon, variants in PAYER_VARIANTS.items() for v in variants}
DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y", "%Y%m%d"]


@dataclass
class CleanResult:
    data: pd.DataFrame
    audit: list[str] = field(default_factory=list)


def drop_exact_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    out = df.drop_duplicates()
    return out, f"drop_exact_duplicates: removed {len(df) - len(out)} duplicate rows"


def trim_whitespace(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    out = df.copy()
    changed = 0
    for col in [c for c in out.columns if pd.api.types.is_string_dtype(out[c])]:
        stripped = out[col].str.strip()
        changed += int((stripped != out[col]).sum())
        out[col] = stripped
    return out, f"trim_whitespace: trimmed {changed} values"


def parse_dates(df: pd.DataFrame, cols=("service_date", "submission_date")) -> tuple[pd.DataFrame, str]:
    out = df.copy()
    unparsed = 0
    for col in cols:
        parsed = pd.Series(pd.NaT, index=out.index, dtype="datetime64[ns]")
        for fmt in DATE_FORMATS:
            mask = parsed.isna()
            parsed[mask] = pd.to_datetime(out.loc[mask, col], format=fmt, errors="coerce")
        unparsed += int(parsed.isna().sum())
        out[col] = parsed
    return out, f"parse_dates: standardised {len(cols)} date columns from {len(DATE_FORMATS)} formats ({unparsed} unparseable)"


def parse_amounts(df: pd.DataFrame, cols=("billed_amount", "allowed_amount")) -> tuple[pd.DataFrame, str]:
    out = df.copy()
    fixed = 0
    for col in cols:
        raw = out[col].astype(str)
        fixed += int(raw.str.contains(r"[$,]").sum())
        out[col] = pd.to_numeric(raw.str.replace(r"[$,]", "", regex=True), errors="coerce")
    return out, f"parse_amounts: stripped currency symbols from {fixed} values"


def standardise_payers(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    out = df.copy()
    mapped = out["payer_name"].map(lambda s: PAYER_LOOKUP.get(_norm(s)))
    changed = int((mapped != out["payer_name"]).sum())
    out["payer_name"] = mapped.fillna(out["payer_name"])
    return out, f"standardise_payers: mapped {changed} payer name variants to {mapped.nunique()} payers"


def standardise_status(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    out = df.copy()
    before = out["claim_status"].nunique()
    out["claim_status"] = out["claim_status"].str.strip().str.lower()
    return out, f"standardise_status: {before} spellings -> {out['claim_status'].nunique()} statuses"


PIPELINE = [
    drop_exact_duplicates,
    trim_whitespace,
    parse_dates,
    parse_amounts,
    standardise_payers,
    standardise_status,
]


def clean(df: pd.DataFrame) -> CleanResult:
    result = CleanResult(df)
    for step in PIPELINE:
        result.data, line = step(result.data)
        result.audit.append(line)
    return result
