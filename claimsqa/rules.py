"""Declarative QA rules for cleaned claims.

Each rule is a name, a severity and a function that returns a boolean mask of
*failing* rows. Adding a check means adding one line to RULES.

Severity:
    critical - the row cannot be used for benchmarking (quarantined)
    warning  - the row is usable but should be reviewed
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

CPT_PATTERN = r"^\d{5}$"
ICD10_PATTERN = r"^[A-TV-Z]\d{2}(\.[A-Z0-9]{1,4})?$"
VALID_STATUS = {"paid", "denied", "pending"}


@dataclass(frozen=True)
class Rule:
    name: str
    severity: str
    description: str
    check: Callable[[pd.DataFrame], pd.Series]


def _today() -> pd.Timestamp:
    return pd.Timestamp("2026-01-31")  # extract "as of" date; fixed for reproducibility


RULES = [
    Rule("claim_id_unique", "critical", "Each claim ID appears once",
         lambda d: d["claim_id"].duplicated(keep=False)),
    Rule("member_id_present", "critical", "Member ID is populated",
         lambda d: d["member_id"].fillna("").eq("")),
    Rule("dates_parseable", "critical", "Service and submission dates are valid dates",
         lambda d: d["service_date"].isna() | d["submission_date"].isna()),
    Rule("service_not_in_future", "critical", "Date of service is not after the extract date",
         lambda d: d["service_date"] > _today()),
    Rule("submitted_after_service", "critical", "Claim is not submitted before the date of service",
         lambda d: d["submission_date"] < d["service_date"]),
    Rule("cpt_format", "critical", "CPT code is exactly 5 digits",
         lambda d: ~d["cpt_code"].astype(str).str.match(CPT_PATTERN)),
    Rule("icd10_format", "critical", "ICD-10 code has a valid structure (e.g. E11.9)",
         lambda d: ~d["icd10_code"].astype(str).str.match(ICD10_PATTERN)),
    Rule("billed_positive", "critical", "Billed amount is a positive number",
         lambda d: d["billed_amount"].isna() | (d["billed_amount"] <= 0)),
    Rule("allowed_not_above_billed", "warning", "Allowed amount does not exceed billed amount",
         lambda d: d["allowed_amount"] > d["billed_amount"]),
    Rule("status_valid", "critical", "Status is paid, denied or pending",
         lambda d: ~d["claim_status"].isin(VALID_STATUS)),
    Rule("payer_known", "warning", "Payer maps to a known payer",
         lambda d: ~d["payer_name"].isin(["BlueStar Health", "United Care Plus", "Medicare", "Medicaid", "Self-Pay"])),
    Rule("late_submission", "warning", "Submitted within 30 days of service",
         lambda d: (d["submission_date"] - d["service_date"]).dt.days > 30),
]


def run_rules(df: pd.DataFrame, rules=RULES) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (summary per rule, row-level failures)."""
    summary, failures = [], []
    for rule in rules:
        mask = rule.check(df).fillna(True).astype(bool)
        n_fail = int(mask.sum())
        summary.append({
            "rule": rule.name,
            "severity": rule.severity,
            "description": rule.description,
            "failed_rows": n_fail,
            "pass_rate_pct": round(100 * (1 - n_fail / len(df)), 2) if len(df) else 100.0,
            "status": "PASS" if n_fail == 0 else "FAIL",
        })
        if n_fail:
            f = df.loc[mask, ["claim_id"]].copy()
            f["rule"], f["severity"] = rule.name, rule.severity
            failures.append(f)
    fail_df = pd.concat(failures, ignore_index=True) if failures else pd.DataFrame(columns=["claim_id", "rule", "severity"])
    return pd.DataFrame(summary), fail_df


def split_clean_and_quarantine(df: pd.DataFrame, failures: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rows with any critical failure go to quarantine; the rest are benchmark-ready."""
    bad_ids = set(failures.loc[failures.severity == "critical", "claim_id"])
    bad = df["claim_id"].isin(bad_ids)
    return df[~bad].copy(), df[bad].copy()
