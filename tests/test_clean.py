import pandas as pd

from claimsqa.clean import clean, parse_amounts, parse_dates, standardise_payers


def test_parse_dates_handles_all_formats():
    df = pd.DataFrame({"service_date": ["2025-03-04", "03/04/2025", "04-Mar-2025", "20250304"],
                       "submission_date": ["2025-03-05"] * 4})
    out, _ = parse_dates(df)
    assert out.service_date.nunique() == 1
    assert out.service_date.iloc[0] == pd.Timestamp("2025-03-04")


def test_parse_amounts_strips_currency():
    df = pd.DataFrame({"billed_amount": ["$1,234.50", "99.9", "-12"], "allowed_amount": ["1", "2", "3"]})
    out, log = parse_amounts(df)
    assert out.billed_amount.tolist() == [1234.5, 99.9, -12.0]
    assert "1 values" in log


def test_payer_variants_collapse_to_canonical_names():
    df = pd.DataFrame({"payer_name": ["BLUESTAR HEALTH", "Bluestar Hlth", "UNITED CARE+", "selfpay", "Patient"]})
    out, _ = standardise_payers(df)
    assert out.payer_name.tolist() == ["BlueStar Health", "BlueStar Health", "United Care Plus", "Self-Pay", "Self-Pay"]


def test_full_pipeline_removes_duplicates_and_logs_every_step(raw_extract):
    result = clean(raw_extract)
    assert len(result.data) < len(raw_extract)
    assert not result.data.duplicated().any()
    assert len(result.audit) == 6
    assert set(result.data.claim_status) <= {"paid", "denied", "pending"}
