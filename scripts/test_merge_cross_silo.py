"""
One query per home department (as Department Head) designed to match documents
in a *merged* silo (not the active home silo). Run from repo root:
  python scripts/test_merge_cross_silo.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.SearchWorker import SearchWorker
from core.Utils import (
    CONFIG,
    get_org_config,
    merge_credit_cross_access_subset,
    merge_hr_cross_access_subset,
    merge_it_cross_access_subset,
    merge_ops_cross_access_subset,
    merge_risk_silo_cross_access_subset,
)

ROLE = "Department Head (VP)"
VAULT = CONFIG["CLEANED_DATA_PATH"]


def build_allowed_subsets(active_dept: str, departments: list[str]) -> list[str]:
    if "General" in departments and active_dept != "General":
        return [active_dept, "General"]
    return [active_dept]


def apply_all_merges(subsets: list[str], active_dept: str) -> list[str]:
    s = merge_credit_cross_access_subset(subsets, ROLE, active_dept)
    s = merge_hr_cross_access_subset(s, ROLE, active_dept)
    s = merge_it_cross_access_subset(s, ROLE, active_dept)
    s = merge_ops_cross_access_subset(s, ROLE, active_dept)
    s = merge_risk_silo_cross_access_subset(s, ROLE, active_dept)
    return s if isinstance(s, list) else subsets


def main() -> None:
    org = get_org_config()
    departments = [d["name"] for d in org.get("departments", []) if isinstance(d, dict)]

    cases: list[tuple[str, str, str]] = [
        # home_dept, expected_foreign_silo, intent label
        (
            "Credit & Loans",
            "HR & Admin",
            "Merged HR (HRP bonus policy, universal/whitelist)",
        ),
        (
            "HR & Admin",
            "Credit & Loans",
            "Merged Credit (policy_strategy whitelist for HR head)",
        ),
        (
            "IT & Digital",
            "Operations",
            "Merged Ops (OPS-001 Paragon branch report)",
        ),
        (
            "Operations",
            "Risk & Compliance",
            "Merged Risk (strategy / AML overview docs)",
        ),
        (
            "Risk & Compliance",
            "IT & Digital",
            "Merged IT (ITD maintenance / security whitelist)",
        ),
    ]

    worker = SearchWorker(VAULT)
    rows = []

    for home, expect_silo, label in cases:
        subsets = build_allowed_subsets(home, departments)
        merged = apply_all_merges(subsets, home)

        # SearchWorker matches one lowercase keyword against title/tags/summary.
        kw_map = {
            "Credit & Loans": "bonus",
            "HR & Admin": "collateral",
            "IT & Digital": "paragon",
            "Operations": "aml",
            "Risk & Compliance": "maintenance",
        }
        kw = kw_map[home]
        hits = worker.search(
            kw,
            allowed_subsets=merged,
            viewer_role=ROLE,
            viewer_active_department=home,
        )

        foreign_hits = [h for h in hits if h.get("department") == expect_silo]
        top_depts = sorted({h.get("department") for h in hits})

        rows.append(
            {
                "home_dept": home,
                "keyword_used": kw,
                "merged_silos": merged,
                "expect_cross_silo": expect_silo,
                "foreign_hits": len(foreign_hits),
                "total_hits": len(hits),
                "top_titles": [h.get("title", "")[:60] for h in foreign_hits[:3]],
                "label": label,
                "depts_in_results": top_depts,
            }
        )

    # Print report
    print("=== Merge cross-silo search test (Department Head) ===\n")
    for r in rows:
        ok = r["foreign_hits"] > 0
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] Active: {r['home_dept']}")
        print(f"       Intent: {r['label']}")
        print(f"       Keyword: {r['keyword_used']!r}")
        print(f"       Merged scope ({len(r['merged_silos'])} silos): {', '.join(r['merged_silos'])}")
        print(f"       Expected hits in: {r['expect_cross_silo']} — got {r['foreign_hits']} (total hits {r['total_hits']})")
        if r["top_titles"]:
            print(f"       Sample titles: {r['top_titles']}")
        print(f"       Departments seen in hit set: {r['depts_in_results']}")
        print()

    failed = sum(1 for r in rows if r["foreign_hits"] == 0)
    print(f"Summary: {len(rows) - failed}/{len(rows)} cross-silo keyword tests returned ≥1 hit in target merged silo.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
