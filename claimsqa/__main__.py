"""Command-line entry point.

    python -m claimsqa generate            # write data/raw_claims_extract.csv
    python -m claimsqa run                 # clean + QA, write reports/
    python -m claimsqa run --input my.csv --fail-on-critical
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

from .clean import clean
from .generate import generate_extract
from .report import build_summary, write_reports
from .rules import run_rules, split_clean_and_quarantine

DEFAULT_INPUT = Path("data/raw_claims_extract.csv")


def cmd_generate(args) -> int:
    df = generate_extract(n=args.rows)
    DEFAULT_INPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(DEFAULT_INPUT, index=False)
    print(f"Wrote {len(df):,} rows to {DEFAULT_INPUT}")
    return 0


def cmd_run(args) -> int:
    t0 = time.perf_counter()
    raw = pd.read_csv(args.input, dtype=str, keep_default_na=False)
    result = clean(raw)
    rule_summary, failures = run_rules(result.data)
    ready, quarantine = split_clean_and_quarantine(result.data, failures)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ready.to_csv(out / "claims_benchmark_ready.csv", index=False)
    quarantine.to_csv(out / "claims_quarantine.csv", index=False)
    summary = build_summary(len(raw), len(result.data), ready, quarantine, rule_summary, result.audit)
    write_reports(summary, failures, out)

    print("Cleaning:")
    for line in result.audit:
        print(f"  - {line}")
    print("\nQA rules:")
    print(rule_summary[["rule", "severity", "failed_rows", "status"]].to_string(index=False))
    print(f"\n{len(ready):,} of {len(result.data):,} rows benchmark-ready ({summary['ready_pct']}%), "
          f"{len(quarantine):,} quarantined. Finished in {time.perf_counter() - t0:.2f}s.")
    print(f"Reports in {out}/ (open qa_report.html)")

    critical_fail = (rule_summary.severity.eq("critical") & rule_summary.status.eq("FAIL")).any()
    return 1 if args.fail_on_critical and critical_fail else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="claimsqa", description="Clean and QA claims extracts.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="create a synthetic messy extract")
    g.add_argument("--rows", type=int, default=2500)
    g.set_defaults(func=cmd_generate)
    r = sub.add_parser("run", help="clean the extract and run QA rules")
    r.add_argument("--input", default=DEFAULT_INPUT)
    r.add_argument("--out", default="reports")
    r.add_argument("--fail-on-critical", action="store_true", help="exit 1 if any critical rule fails")
    r.set_defaults(func=cmd_run)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
