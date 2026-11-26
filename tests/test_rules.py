import pandas as pd

from claimsqa.clean import clean
from claimsqa.rules import run_rules, split_clean_and_quarantine


def _row(**kw):
    base = dict(claim_id="C1", member_id="M1", payer_name="Medicare", cpt_code="99213",
                icd10_code="E11.9", service_date=pd.Timestamp("2025-05-01"),
                submission_date=pd.Timestamp("2025-05-03"), billed_amount=200.0,
                allowed_amount=150.0, claim_status="paid")
    base.update(kw)
    return base


def _fails(**kw):
    summary, _ = run_rules(pd.DataFrame([_row(**kw)]))
    return set(summary.loc[summary.status == "FAIL", "rule"])


def test_clean_row_passes_everything():
    assert _fails() == set()


def test_each_defect_trips_its_rule():
    assert "cpt_format" in _fails(cpt_code="9921")
    assert "icd10_format" in _fails(icd10_code="E119")
    assert "member_id_present" in _fails(member_id="")
    assert "submitted_after_service" in _fails(submission_date=pd.Timestamp("2025-04-20"))
    assert "service_not_in_future" in _fails(service_date=pd.Timestamp("2027-01-01"),
                                             submission_date=pd.Timestamp("2027-01-02"))
    assert "billed_positive" in _fails(billed_amount=-5.0)
    assert "allowed_not_above_billed" in _fails(allowed_amount=300.0)


def test_only_critical_failures_are_quarantined():
    df = pd.DataFrame([_row(claim_id="A"), _row(claim_id="B", cpt_code="X"),
                       _row(claim_id="C", allowed_amount=999.0)])
    _, failures = run_rules(df)
    ready, quarantine = split_clean_and_quarantine(df, failures)
    assert quarantine.claim_id.tolist() == ["B"]          # critical
    assert ready.claim_id.tolist() == ["A", "C"]           # warning only stays


def test_generated_extract_end_to_end(raw_extract):
    data = clean(raw_extract).data
    summary, failures = run_rules(data)
    ready, quarantine = split_clean_and_quarantine(data, failures)
    assert len(ready) + len(quarantine) == len(data)
    assert 0.85 < len(ready) / len(data) < 0.99   # defects injected at ~7%
    assert summary.set_index("rule").loc["claim_id_unique", "status"] == "PASS"
