#!/usr/bin/env python3
"""
Smoke test: for each org role, verify search finds documents and optionally run full GURU.

Usage:
  python scripts/guru_role_smoke_test.py              # search-only (no API bill)
  python scripts/guru_role_smoke_test.py --full       # calls LLM per role (needs keys in config/.env)

Requires: run from repo root with venv active.
"""
from __future__ import annotations

import argparse
import os
import sys

# Repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.SearchWorker import SearchWorker  # noqa: E402
from core.Utils import CONFIG  # noqa: E402


CASES = [
    {
        "role": "CEO (Chief Executive Officer)",
        "scope": "ALL",
        "department_note": "",
        "question": "What loan approval thresholds or secondary sign-off rules apply to high-value requests?",
        "probe_keywords": ["loan", "approval"],
    },
    {
        "role": "CFO (Chief Financial Officer)",
        "scope": ["Credit & Loans", "Risk & Compliance", "General"],
        "department_note": "multi-silo",
        "question": "What collateral valuation or lending policy monitoring actions are documented?",
        "probe_keywords": ["collateral", "lending"],
    },
    {
        "role": "CTO (Chief Technology Officer)",
        "scope": ["IT & Digital", "Operations", "General"],
        "department_note": "multi-silo",
        "question": "What firewall or database monitoring measures are described for IT systems?",
        "probe_keywords": ["firewall", "database"],
    },
    {
        "role": "Department Head (VP)",
        "scope": ["Operations"],
        "department_note": "pick Operations as Active Department in UI",
        "question": "How are branch operations efficiency or cash flow optimization addressed?",
        "probe_keywords": ["cash", "operations"],
    },
    {
        "role": "Operational Staff",
        "scope": ["HR & Admin"],
        "department_note": "pick HR & Admin as Active Department in UI",
        "question": "What employee welfare or benefits policy areas are covered in HR documents?",
        "probe_keywords": ["welfare", "benefits"],
    },
]


def search_hit_count(worker: SearchWorker, keywords: list[str], scope) -> tuple[int, str]:
    """Union of hits across probe keywords (dedupe by path)."""
    seen: set[str] = set()
    total = 0
    sample = ""
    for kw in keywords:
        if scope == "ALL":
            # SearchWorker expects list or ALL
            hits = worker.search(kw, "ALL")
        else:
            hits = worker.search(kw, scope)
        for h in hits:
            if h["path"] not in seen:
                seen.add(h["path"])
                total += 1
                if not sample:
                    sample = (h.get("doc_id"), h.get("title", ""))[:120]
    return total, str(sample)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="Run RAGOrchestrator (LLM) per case; needs API keys.")
    args = parser.parse_args()

    worker = SearchWorker(CONFIG["CLEANED_DATA_PATH"])
    failed = False

    print("=== Phase A: deterministic search (cache-aware) ===\n")
    for case in CASES:
        n, sample = search_hit_count(worker, case["probe_keywords"], case["scope"])
        ok = n > 0
        failed |= not ok
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {case['role']}")
        print(f"       scope: {case['scope']}")
        print(f"       keywords: {case['probe_keywords']} -> {n} unique doc(s)")
        if sample:
            print(f"       sample: {sample}")
        print(f"       suggested Q: {case['question']}")
        print()

    if failed:
        print("Search phase FAILED — fix vault paths, rebuild index, or SearchWorker.\n")
        return 1

    if not args.full:
        print("Search phase OK. Run with --full to test GURU end-to-end (uses your API quota).\n")
        return 0

    has_key = bool(
        CONFIG.get("GEMINI_API_KEY")
        or CONFIG.get("OPENAI_API_KEY")
        or CONFIG.get("ANTHROPIC_API_KEY")
    )
    if not has_key:
        print("No GEMINI_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY in config/.env — skip --full.\n")
        return 1

    from core.Orchestrator import RAGOrchestrator  # noqa: E402

    orch = RAGOrchestrator(CONFIG["CLEANED_DATA_PATH"])
    print("=== Phase B: GURU synthesis (LLM) ===\n")

    for case in CASES:
        print(f"--- {case['role']} ---")
        try:
            out = orch.handle_request(case["question"], case["scope"])
            ans = out.get("answer", "")[:400]
            src_n = len(out.get("sources") or [])
            print(f"sources: {src_n}")
            print(f"answer_preview:\n{ans}\n")
        except Exception as e:
            print(f"ERROR: {e}\n")
            return 1

    print("Full GURU smoke completed.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
