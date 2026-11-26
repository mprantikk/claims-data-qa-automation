"""Render the QA run as a self-contained HTML "failure panel" plus JSON."""

from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd

CSS = """
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#f6f7f9;color:#1f2937}
header{background:#0f172a;color:#fff;padding:24px 32px}
header h1{margin:0;font-size:22px} header p{margin:6px 0 0;color:#94a3b8;font-size:14px}
main{max-width:1000px;margin:0 auto;padding:24px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:24px}
.kpi{background:#fff;border-radius:10px;padding:16px;box-shadow:0 1px 2px rgba(0,0,0,.06)}
.kpi .v{font-size:26px;font-weight:700} .kpi .l{font-size:12px;color:#6b7280;text-transform:uppercase;letter-spacing:.04em}
section{background:#fff;border-radius:10px;padding:18px 20px;margin-bottom:20px;box-shadow:0 1px 2px rgba(0,0,0,.06)}
h2{font-size:16px;margin:0 0 12px}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:8px;border-bottom:1px solid #eef0f3} th{color:#6b7280;font-weight:600;font-size:12px;text-transform:uppercase}
.pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;font-weight:600}
.PASS{background:#dcfce7;color:#166534}.FAIL{background:#fee2e2;color:#991b1b}
.critical{color:#991b1b}.warning{color:#92400e}
.bar{height:8px;background:#eef0f3;border-radius:4px;overflow:hidden}.bar i{display:block;height:100%;background:#16a34a}
ul{margin:0;padding-left:18px;font-size:14px;line-height:1.7}
"""


def build_summary(raw_rows: int, clean_rows: int, ready: pd.DataFrame, quarantine: pd.DataFrame,
                  rule_summary: pd.DataFrame, audit: list[str]) -> dict:
    return {
        "raw_rows": raw_rows,
        "rows_after_cleaning": clean_rows,
        "benchmark_ready_rows": len(ready),
        "quarantined_rows": len(quarantine),
        "ready_pct": round(100 * len(ready) / clean_rows, 1) if clean_rows else 0.0,
        "rules_run": len(rule_summary),
        "rules_failed": int((rule_summary.status == "FAIL").sum()),
        "audit": audit,
        "rules": rule_summary.to_dict(orient="records"),
    }


def write_reports(summary: dict, failures: pd.DataFrame, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "qa_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    failures.to_csv(out_dir / "qa_failures.csv", index=False)
    (out_dir / "qa_report.html").write_text(render_html(summary, failures))


def render_html(s: dict, failures: pd.DataFrame) -> str:
    kpis = [
        (f"{s['raw_rows']:,}", "Rows in extract"),
        (f"{s['benchmark_ready_rows']:,}", "Benchmark-ready"),
        (f"{s['quarantined_rows']:,}", "Quarantined"),
        (f"{s['ready_pct']}%", "Ready rate"),
        (f"{s['rules_run'] - s['rules_failed']}/{s['rules_run']}", "Rules fully passing"),
    ]
    kpi_html = "".join(f'<div class="kpi"><div class="v">{v}</div><div class="l">{l}</div></div>' for v, l in kpis)
    rule_rows = "".join(
        f"<tr><td><b>{html.escape(r['rule'])}</b><br><small>{html.escape(r['description'])}</small></td>"
        f"<td class='{r['severity']}'>{r['severity']}</td><td>{r['failed_rows']}</td>"
        f"<td><div class='bar'><i style='width:{r['pass_rate_pct']}%'></i></div>{r['pass_rate_pct']}%</td>"
        f"<td><span class='pill {r['status']}'>{r['status']}</span></td></tr>"
        for r in s["rules"]
    )
    sample = failures.head(25)
    fail_rows = "".join(
        f"<tr><td>{html.escape(str(r.claim_id))}</td><td>{html.escape(r.rule)}</td><td class='{r.severity}'>{r.severity}</td></tr>"
        for r in sample.itertuples()
    ) or "<tr><td colspan=3>No failures</td></tr>"
    audit = "".join(f"<li>{html.escape(a)}</li>" for a in s["audit"])
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Claims QA report</title><style>{CSS}</style></head>
<body><header><h1>Claims data QA report</h1><p>Automated cleaning and integrity checks · synthetic data</p></header>
<main><div class="kpis">{kpi_html}</div>
<section><h2>Integrity checks</h2><table><tr><th>Rule</th><th>Severity</th><th>Failed</th><th>Pass rate</th><th>Status</th></tr>{rule_rows}</table></section>
<section><h2>Cleaning audit trail</h2><ul>{audit}</ul></section>
<section><h2>Failure sample (first 25 of {len(failures)})</h2><table><tr><th>Claim</th><th>Rule</th><th>Severity</th></tr>{fail_rows}</table></section>
</main></body></html>"""
