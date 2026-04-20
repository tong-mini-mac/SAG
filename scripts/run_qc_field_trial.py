#!/usr/bin/env python3
"""
Field-style QC trial: 3 org roles x 3 questions = 9 runs.
  python scripts/run_qc_field_trial.py --mock
  python scripts/run_qc_field_trial.py --live --provider google    # GEMINI_API_KEY
  python scripts/run_qc_field_trial.py --live --provider openai   # OPENAI_API_KEY
  python scripts/run_qc_field_trial.py --live --provider anthropic # ANTHROPIC_API_KEY
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

os.environ.setdefault("PYTHONIOENCODING", "utf-8")


class MockLLM:
    """Deterministic stand-in for Gemini/OpenAI in --mock mode."""

    def __init__(self):
        self._qc_round = 0

    def call(self, prompt, system_instruction=None, json_mode=False):
        si = system_instruction or ""
        if json_mode and "Semantic Swarm" in si:
            return '["loan", "policy", "approval", "demo"]'
        if json_mode and "Industrial Audit Judge" in si:
            self._qc_round += 1
            patterns = [
                (4, 3, "Strong alignment with GEN-001; tighten opening sentence."),
                (4, 4, "Balanced accuracy and tone versus GEN-001."),
                (5, 4, "Excellent grounding in GEN-001; minor redundancy in closing."),
            ]
            a, lang, crit = patterns[(self._qc_round - 1) % 3]
            total = a + lang
            return json.dumps(
                {
                    "accuracy_score": a,
                    "language_score": lang,
                    "qc_score": total,
                    "critique": crit,
                    "hallucination_detected": False,
                    "tone_grade": "A" if total >= 9 else "B",
                }
            )
        if "Global Enterprise GURU" in si:
            return (
                "Per [GEN-001] Company Demo Policy, internal loan requests exceeding one million baht "
                "require secondary approval from the credit committee. "
                "Executive insight: align origination workflows with this delegated threshold before disbursement."
            )
        if "Refine the provided response" in si:
            return (
                "Per [GEN-001] Company Demo Policy, loan requests above one million baht require secondary approval. "
                "Action: route files to the credit committee prior to release, maintaining audit-ready documentation."
            )
        if json_mode:
            return "[]"
        return "(mock) No LLM content for this call shape."


def _patch_mock():
    import core.Utils as U

    _singleton: list[MockLLM | None] = [None]

    def _fake_client():
        if _singleton[0] is None:
            _singleton[0] = MockLLM()
        return _singleton[0]

    U.LLMInterface.get_client = staticmethod(_fake_client)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="Use mock LLM (no API key)")
    parser.add_argument("--live", action="store_true", help="Use real API keys from env / config/.env")
    parser.add_argument(
        "--provider",
        choices=("google", "openai", "anthropic"),
        default="google",
        help="LLM vendor for --live (sets RAGD_PRIMARY_PROVIDER for CLI fallback in LLMInterface)",
    )
    args = parser.parse_args()
    if args.mock and args.live:
        print("Choose only one of --mock or --live", file=sys.stderr)
        sys.exit(2)
    if not args.mock and not args.live:
        args.mock = True

    from dotenv import load_dotenv

    load_dotenv(os.path.join(ROOT, "config", ".env"))
    load_dotenv(os.path.join(ROOT, "..", ".env"))

    if args.live:
        os.environ["RAGD_PRIMARY_PROVIDER"] = args.provider
        if args.provider == "google":
            key_name, key = "GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", "").strip()
        elif args.provider == "openai":
            key_name, key = "OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", "").strip()
        else:
            key_name, key = "ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not key:
            print(
                f"{key_name} missing for --provider {args.provider}. "
                f"Set it in config/.env or the environment, or run with --mock.",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        _patch_mock()

    from core.Orchestrator import RAGOrchestrator
    from core.AuditJudge import AuditJudge

    trials = [
        {
            "role": "CEO (Chief Executive Officer)",
            "scope": "ALL",
            "questions": [
                "What is our internal rule for large loan approvals?",
                "Summarize loan approval thresholds mentioned in General policy.",
                "Which committee must sign off on high-value loans per demo policy?",
            ],
        },
        {
            "role": "CFO (Chief Financial Officer)",
            "scope": ["Credit & Loans", "Risk & Compliance", "General"],
            "questions": [
                "Do we have a written threshold for loan secondary approval?",
                "List keywords we should track for credit policy compliance.",
                "What does GEN-001 say about amounts requiring extra approval?",
            ],
        },
        {
            "role": "Operational Staff",
            "scope": ["General"],
            "dept_label": "General",
            "questions": [
                "As staff in General, what loan amount triggers secondary approval?",
                "Where is the demo loan policy documented?",
                "What is the title of the internal demo policy for loans?",
            ],
        },
    ]

    orc = RAGOrchestrator()
    judge = AuditJudge()
    rows = []

    mode = f"--live --provider {args.provider}" if args.live else "--mock"
    print(f"RAG-Destroyer QC field trial (9 requests) [{mode}]\n")
    for block in trials:
        scope = block["scope"]
        label = f"{block['role']} | scope={scope}"
        print(f"--- {label} ---")
        for i, q in enumerate(block["questions"], 1):
            result = orc.handle_request(q, scope)
            qc = judge.evaluate(q, result["sources"], result["answer"])
            rows.append(
                {
                    "role": block["role"],
                    "q_index": i,
                    "query": q[:70] + ("…" if len(q) > 70 else ""),
                    "n_sources": len(result.get("sources") or []),
                    "qc_score": qc.get("qc_score"),
                    "accuracy": qc.get("accuracy_score"),
                    "language": qc.get("language_score"),
                    "tone": qc.get("tone_grade"),
                }
            )
            print(
                f"  Q{i}: qc={qc.get('qc_score')} acc={qc.get('accuracy_score')} lang={qc.get('language_score')} "
                f"src={len(result.get('sources') or [])} | {q[:60]}…"
            )
        print()

    out_path = os.path.join(ROOT, "logs", "qc_field_trial.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    print(f"Wrote summary: {out_path}")
    if args.mock:
        print(
            "\n(--mock) LLM calls were stubbed. For real API + QC, e.g.:\n"
            "  python scripts/run_qc_field_trial.py --live --provider google\n"
            "  python scripts/run_qc_field_trial.py --live --provider openai\n"
            "  python scripts/run_qc_field_trial.py --live --provider anthropic"
        )


if __name__ == "__main__":
    main()
