"""Generate a messy, synthetic EHR claims extract.

Real extracts from practice-management systems arrive with mixed date
formats, free-text payer names, stray whitespace, duplicated rows and the
occasional impossible value. This generator reproduces those problems on
purpose (with a fixed seed) so the cleaning and QA steps have real work to do.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

import pandas as pd

PAYER_VARIANTS = {
    "BlueStar Health": ["BlueStar Health", "BLUESTAR HEALTH", "Bluestar Hlth", " BlueStar Health "],
    "United Care Plus": ["United Care Plus", "UNITED CARE+", "united care plus", "UCP"],
    "Medicare": ["Medicare", "MEDICARE PART B", "Medicare B", "CMS Medicare"],
    "Medicaid": ["Medicaid", "STATE MEDICAID", "Medicaid (State)"],
    "Self-Pay": ["Self-Pay", "SELF PAY", "selfpay", "Patient"],
}
CPT_CODES = ["99213", "99214", "99215", "93000", "73721", "71046", "11102", "20610", "36415"]
ICD10 = ["E11.9", "I10", "M54.5", "J06.9", "Z00.00", "R07.9", "K21.9", "F41.1"]
DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y", "%Y%m%d"]


def _fmt(d: date, rng: random.Random) -> str:
    return d.strftime(rng.choice(DATE_FORMATS))


def generate_extract(n: int = 2500, seed: int = 7) -> pd.DataFrame:
    rng = random.Random(seed)
    start = date(2025, 1, 1)
    rows = []
    for i in range(1, n + 1):
        payer = rng.choice(list(PAYER_VARIANTS))
        dos = start + timedelta(days=rng.randint(0, 364))
        sub = dos + timedelta(days=max(0, int(rng.gauss(4, 3))))
        billed = round(rng.uniform(60, 900), 2)
        allowed = round(billed * rng.uniform(0.5, 0.9), 2)
        row = {
            "claim_id": f"CLM{i:06d}",
            "member_id": f"M{rng.randint(10000, 99999)}",
            "payer_name": rng.choice(PAYER_VARIANTS[payer]),
            "cpt_code": rng.choice(CPT_CODES),
            "icd10_code": rng.choice(ICD10),
            "service_date": _fmt(dos, rng),
            "submission_date": _fmt(sub, rng),
            "billed_amount": f"${billed:,.2f}" if rng.random() < 0.3 else str(billed),
            "allowed_amount": str(allowed),
            "claim_status": rng.choice(["Paid", "PAID", "paid ", "Denied", "denied", "Pending"]),
        }
        # inject defects at realistic, low rates
        r = rng.random()
        if r < 0.02:
            row["member_id"] = ""
        elif r < 0.035:
            row["cpt_code"] = rng.choice(["9921", "ABCDE", "992134"])
        elif r < 0.05:
            row["icd10_code"] = rng.choice(["E119", "10", "XX.1"])
        elif r < 0.06:
            row["allowed_amount"] = str(round(billed * 1.3, 2))  # allowed above billed
        elif r < 0.07:
            row["submission_date"] = _fmt(dos - timedelta(days=rng.randint(1, 10)), rng)
        elif r < 0.075:
            row["service_date"] = _fmt(date(2027, 3, 1), rng)  # future date of service
        elif r < 0.08:
            row["billed_amount"] = "-" + row["billed_amount"].lstrip("$")
        rows.append(row)

    df = pd.DataFrame(rows)
    # exact duplicates, as produced by re-run exports
    dupes = df.sample(n=max(1, n // 50), random_state=seed)
    return pd.concat([df, dupes], ignore_index=True)
