import os
import re
import json
import time
import shutil
import frontmatter
from dotenv import load_dotenv

# Dynamic Root Resolution (GitHub Ready)
ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Load Environment
def load_env_config():
    """Loads industrial configuration with support for centralized workspace secrets."""
    # 1. Load project-local .env
    local_env = os.path.join(ROOT_PATH, "config", ".env")
    if os.path.exists(local_env):
        load_dotenv(local_env)
        
    # 2. Load centralized workspace .env (Parent Directory: MyClaw)
    central_env = os.path.abspath(os.path.join(ROOT_PATH, "..", ".env"))
    if os.path.exists(central_env):
        load_dotenv(central_env, override=True) # Centralized vault can override locals for industrial consistency
    
    return {
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
        "GEMINI_MODEL": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "OPENAI_MODEL": os.getenv("OPENAI_MODEL", "gpt-4o"),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "ANTHROPIC_MODEL": os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620"),
        "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN"),
        
        # Paths - Default to project relative but allow override
        "RAW_DATA_PATH": os.getenv("RAW_DATA_PATH", os.path.join(ROOT_PATH, "raw_data")),
        "CLEANED_DATA_PATH": os.getenv("CLEANED_DATA_PATH", os.path.join(ROOT_PATH, "knowledge")),
        "ORG_STRUCTURE_PATH": os.path.join(ROOT_PATH, "config", "org_structure.json"),
        "LINE_NOTIFY_TOKEN": os.getenv("LINE_NOTIFY_TOKEN"),
        "DISCORD_WEBHOOK_URL": os.getenv("DISCORD_WEBHOOK_URL"),
        "AUDIT_LOG_PATH": os.path.join(ROOT_PATH, "logs", "accuracy_audit.json")
    }

CONFIG = load_env_config()

def get_org_config():
    path = CONFIG["ORG_STRUCTURE_PATH"]
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_org_structure(config_dict: dict) -> None:
    """Persist full org JSON (departments, roles, metadata) to config/org_structure.json."""
    path = CONFIG["ORG_STRUCTURE_PATH"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config_dict, f, ensure_ascii=False, indent=2)


def count_markdown_docs_under(dept_folder: str) -> int:
    """Recursive count of *.md under one folder (matches VaultWarden rules: skip _*.md)."""
    if not os.path.isdir(dept_folder):
        return 0
    n = 0
    for root, _, files in os.walk(dept_folder):
        for fname in files:
            if fname.endswith(".md") and not fname.startswith("_"):
                n += 1
    return n


def maybe_seed_demo_vault(root_path: str, vault_path: str) -> bool:
    """
    If the knowledge vault has no markdown yet and demo_knowledge/ exists in the repo,
    copy demo files into vault so a fresh git clone works without manual copy.
    Opt out: create an empty file vault_path/.no_auto_demo
    """
    opt_out = os.path.join(vault_path, ".no_auto_demo")
    if os.path.isfile(opt_out):
        return False
    os.makedirs(vault_path, exist_ok=True)
    if count_markdown_docs_under(vault_path) > 0:
        return False
    demo = os.path.join(root_path, "demo_knowledge")
    if not os.path.isdir(demo) or count_markdown_docs_under(demo) == 0:
        return False
    copied = False
    for root, _, files in os.walk(demo):
        for fname in files:
            if not fname.endswith(".md") or fname.startswith("_"):
                continue
            src = os.path.join(root, fname)
            rel = os.path.relpath(src, demo)
            dst = os.path.join(vault_path, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            copied = True
    return copied


def vault_doc_counts_for_departments(vault_root: str, department_names: list[str]) -> dict[str, int]:
    """Markdown file counts under vault_root/<DepartmentName>/ for each configured department."""
    out = {}
    for name in department_names:
        dept_path = os.path.join(vault_root, name)
        out[name] = count_markdown_docs_under(dept_path)
    return out


def normalize_audience_raw(raw) -> str:
    """
    Maps markdown frontmatter `audience` to a coarse access level.
    - all: everyone who may access the silo folder (default if missing).
    - management: head / C-suite roles only — hidden from Operational Staff even in same silo.
    """
    if raw is None:
        return "all"
    s = str(raw).strip().lower()
    if s in ("", "all", "everyone", "public", "staff", "operational"):
        return "all"
    if s in ("management", "manager", "executive", "leadership", "heads", "confidential"):
        return "management"
    return "all"


def role_is_management_or_above(role: str) -> bool:
    """Roles that may retrieve audience=management documents."""
    r = (role or "").strip()
    if not r or r == "Operational Staff":
        return False
    if any(r.startswith(p) for p in ("CEO", "CFO", "CTO")):
        return True
    if "Department Head" in r:
        return True
    return False


def viewer_may_read_audience(viewer_role: str | None, audience_norm: str) -> bool:
    if viewer_role is None:
        return True
    if audience_norm != "management":
        return True
    return role_is_management_or_above(viewer_role)


_OPERATIONAL_STAFF_DENYLIST: dict[str, frozenset[str]] | None = None


def load_operational_staff_denylist() -> dict[str, frozenset[str]]:
    """Silo -> set of basenames Operational Staff must not see (see config JSON)."""
    global _OPERATIONAL_STAFF_DENYLIST
    if _OPERATIONAL_STAFF_DENYLIST is not None:
        return _OPERATIONAL_STAFF_DENYLIST
    path = os.path.join(ROOT_PATH, "config", "operational_staff_vault_denylist.json")
    out: dict[str, frozenset[str]] = {}
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                for silo, names in raw.items():
                    if isinstance(names, list):
                        out[str(silo)] = frozenset(str(x) for x in names if x)
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            out = {}
    _OPERATIONAL_STAFF_DENYLIST = out
    return out


_UNIVERSAL_READ_BASES: frozenset[str] | None = None


def load_universal_read_basenames() -> frozenset[str]:
    """Basenames that every role may read within an authorized silo (see config JSON)."""
    global _UNIVERSAL_READ_BASES
    if _UNIVERSAL_READ_BASES is not None:
        return _UNIVERSAL_READ_BASES
    path = os.path.join(ROOT_PATH, "config", "universal_read_basenames.json")
    names: list[str] = []
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict) and isinstance(raw.get("basenames"), list):
                names = [str(x) for x in raw["basenames"] if x]
            elif isinstance(raw, list):
                names = [str(x) for x in raw if x]
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            names = []
    _UNIVERSAL_READ_BASES = frozenset(names)
    return _UNIVERSAL_READ_BASES


_CREDIT_HEAD_CROSS: dict | None = None


def load_credit_head_cross_access() -> dict:
    """Cross-silo Credit reads for non-Credit Department Heads (policies/strategies)."""
    global _CREDIT_HEAD_CROSS
    if _CREDIT_HEAD_CROSS is not None:
        return _CREDIT_HEAD_CROSS
    path = os.path.join(ROOT_PATH, "config", "credit_head_cross_access.json")
    if not os.path.isfile(path):
        _CREDIT_HEAD_CROSS = {}
        return _CREDIT_HEAD_CROSS
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        _CREDIT_HEAD_CROSS = raw if isinstance(raw, dict) else {}
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        _CREDIT_HEAD_CROSS = {}
    return _CREDIT_HEAD_CROSS


def merge_credit_cross_access_subset(
    allowed_search_subsets,
    viewer_role: str | None,
    viewer_active_department: str | None,
):
    """
    Department Head of HR/IT/Operations/Risk: add Credit & Loans to search scope for
    policy/strategy alignment (per-file filter in document_visible_to_viewer).
    """
    if allowed_search_subsets == "ALL" or not isinstance(allowed_search_subsets, list):
        return allowed_search_subsets
    if not viewer_role or "Department Head" not in viewer_role:
        return allowed_search_subsets
    cfg = load_credit_head_cross_access()
    merge_for = cfg.get("merge_credit_for_heads_of", [])
    if (
        not viewer_active_department
        or viewer_active_department not in merge_for
        or viewer_active_department == "Credit & Loans"
    ):
        return allowed_search_subsets
    if "Credit & Loans" in allowed_search_subsets:
        return allowed_search_subsets
    out = list(allowed_search_subsets)
    out.append("Credit & Loans")
    return out


_HR_HEAD_CROSS: dict | None = None


def load_hr_head_cross_access() -> dict:
    """Cross-silo HR reads for non–HR Department Heads (policies / performance / workforce planning)."""
    global _HR_HEAD_CROSS
    if _HR_HEAD_CROSS is not None:
        return _HR_HEAD_CROSS
    path = os.path.join(ROOT_PATH, "config", "hr_head_cross_access.json")
    if not os.path.isfile(path):
        _HR_HEAD_CROSS = {}
        return _HR_HEAD_CROSS
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        _HR_HEAD_CROSS = raw if isinstance(raw, dict) else {}
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        _HR_HEAD_CROSS = {}
    return _HR_HEAD_CROSS


def merge_hr_cross_access_subset(
    allowed_search_subsets,
    viewer_role: str | None,
    viewer_active_department: str | None,
):
    """
    Department Head of Credit/IT/Operations/Risk: add HR & Admin for filtered HR reads
    (whitelist in document_visible_to_viewer).
    """
    if allowed_search_subsets == "ALL" or not isinstance(allowed_search_subsets, list):
        return allowed_search_subsets
    if not viewer_role or "Department Head" not in viewer_role:
        return allowed_search_subsets
    cfg = load_hr_head_cross_access()
    merge_for = cfg.get("merge_hr_for_heads_of", [])
    if (
        not viewer_active_department
        or viewer_active_department not in merge_for
        or viewer_active_department == "HR & Admin"
    ):
        return allowed_search_subsets
    if "HR & Admin" in allowed_search_subsets:
        return allowed_search_subsets
    out = list(allowed_search_subsets)
    out.append("HR & Admin")
    return out


_IT_HEAD_CROSS: dict | None = None


def load_it_head_cross_access() -> dict:
    """Cross-silo IT reads for non–IT Department Heads (least-privilege whitelist + Risk extras)."""
    global _IT_HEAD_CROSS
    if _IT_HEAD_CROSS is not None:
        return _IT_HEAD_CROSS
    path = os.path.join(ROOT_PATH, "config", "it_head_cross_access.json")
    if not os.path.isfile(path):
        _IT_HEAD_CROSS = {}
        return _IT_HEAD_CROSS
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        _IT_HEAD_CROSS = raw if isinstance(raw, dict) else {}
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        _IT_HEAD_CROSS = {}
    return _IT_HEAD_CROSS


def _basename_matches_any_substring(basename: str, substrings: list[str]) -> bool:
    lower = basename.lower()
    for s in substrings:
        if not isinstance(s, str) or not s.strip():
            continue
        if s.lower() in lower:
            return True
    return False


def merge_it_cross_access_subset(
    allowed_search_subsets,
    viewer_role: str | None,
    viewer_active_department: str | None,
):
    """
    Department Head of Credit/HR/Operations/Risk: add IT & Digital for filtered IT reads
    (whitelist / Risk extras / deny patterns in document_visible_to_viewer).
    """
    if allowed_search_subsets == "ALL" or not isinstance(allowed_search_subsets, list):
        return allowed_search_subsets
    if not viewer_role or "Department Head" not in viewer_role:
        return allowed_search_subsets
    cfg = load_it_head_cross_access()
    merge_for = cfg.get("merge_it_for_heads_of", [])
    if (
        not viewer_active_department
        or viewer_active_department not in merge_for
        or viewer_active_department == "IT & Digital"
    ):
        return allowed_search_subsets
    if "IT & Digital" in allowed_search_subsets:
        return allowed_search_subsets
    out = list(allowed_search_subsets)
    out.append("IT & Digital")
    return out


_OPS_HEAD_CROSS: dict | None = None


def load_ops_head_cross_access() -> dict:
    """Cross-silo Operations reads for non–Operations Department Heads (strategy / standards; tiered HR & Risk)."""
    global _OPS_HEAD_CROSS
    if _OPS_HEAD_CROSS is not None:
        return _OPS_HEAD_CROSS
    path = os.path.join(ROOT_PATH, "config", "ops_head_cross_access.json")
    if not os.path.isfile(path):
        _OPS_HEAD_CROSS = {}
        return _OPS_HEAD_CROSS
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        _OPS_HEAD_CROSS = raw if isinstance(raw, dict) else {}
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        _OPS_HEAD_CROSS = {}
    return _OPS_HEAD_CROSS


def merge_ops_cross_access_subset(
    allowed_search_subsets,
    viewer_role: str | None,
    viewer_active_department: str | None,
):
    """
    Department Head of Credit/HR/IT/Risk: add Operations for filtered cross-dept reads
    (whitelist, HR/Risk expansions, deny patterns in document_visible_to_viewer).
    """
    if allowed_search_subsets == "ALL" or not isinstance(allowed_search_subsets, list):
        return allowed_search_subsets
    if not viewer_role or "Department Head" not in viewer_role:
        return allowed_search_subsets
    cfg = load_ops_head_cross_access()
    merge_for = cfg.get("merge_ops_for_heads_of", [])
    if (
        not viewer_active_department
        or viewer_active_department not in merge_for
        or viewer_active_department == "Operations"
    ):
        return allowed_search_subsets
    if "Operations" in allowed_search_subsets:
        return allowed_search_subsets
    out = list(allowed_search_subsets)
    out.append("Operations")
    return out


_RISK_SILO_CROSS: dict | None = None


def load_risk_silo_cross_access() -> dict:
    """Cross-silo Risk & Compliance reads for non–Risk Department Heads (policies/strategy; AML for IT/Ops; auditee reports)."""
    global _RISK_SILO_CROSS
    if _RISK_SILO_CROSS is not None:
        return _RISK_SILO_CROSS
    path = os.path.join(ROOT_PATH, "config", "risk_silo_cross_access.json")
    if not os.path.isfile(path):
        _RISK_SILO_CROSS = {}
        return _RISK_SILO_CROSS
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        _RISK_SILO_CROSS = raw if isinstance(raw, dict) else {}
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        _RISK_SILO_CROSS = {}
    return _RISK_SILO_CROSS


def merge_risk_silo_cross_access_subset(
    allowed_search_subsets,
    viewer_role: str | None,
    viewer_active_department: str | None,
):
    """
    Department Head of Credit/HR/IT/Operations: add Risk & Compliance for filtered reads
    (whitelist, IT/Ops AML extras, auditee audit reports — see document_visible_to_viewer).
    """
    if allowed_search_subsets == "ALL" or not isinstance(allowed_search_subsets, list):
        return allowed_search_subsets
    if not viewer_role or "Department Head" not in viewer_role:
        return allowed_search_subsets
    cfg = load_risk_silo_cross_access()
    merge_for = cfg.get("merge_risk_silo_for_heads_of", [])
    if (
        not viewer_active_department
        or viewer_active_department not in merge_for
        or viewer_active_department == "Risk & Compliance"
    ):
        return allowed_search_subsets
    if "Risk & Compliance" in allowed_search_subsets:
        return allowed_search_subsets
    out = list(allowed_search_subsets)
    out.append("Risk & Compliance")
    return out


def document_visible_to_viewer(
    viewer_role: str | None,
    silo: str,
    basename: str,
    audience_raw,
    viewer_active_department: str | None = None,
) -> bool:
    """Universal allowlist; Credit/HR/IT/Ops/Risk silo cross-dept rules; staff denylist; YAML audience."""
    if basename in load_universal_read_basenames():
        return True

    cfg_cr = load_credit_head_cross_access()
    merge_for = cfg_cr.get("merge_credit_for_heads_of", [])
    policy_strategy = frozenset(cfg_cr.get("policy_strategy_basenames", []))
    ops_extra = frozenset(cfg_cr.get("operations_extra_basenames", []))

    if (
        silo == "Credit & Loans"
        and viewer_role
        and "Department Head" in viewer_role
        and viewer_active_department
        and viewer_active_department != "Credit & Loans"
        and viewer_active_department in merge_for
    ):
        if viewer_active_department == "Risk & Compliance":
            aud = normalize_audience_raw(audience_raw)
            return viewer_may_read_audience(viewer_role, aud)
        if viewer_active_department == "Operations":
            if basename in policy_strategy or basename in ops_extra:
                aud = normalize_audience_raw(audience_raw)
                return viewer_may_read_audience(viewer_role, aud)
            return False
        if viewer_active_department in ("HR & Admin", "IT & Digital"):
            if basename in policy_strategy:
                aud = normalize_audience_raw(audience_raw)
                return viewer_may_read_audience(viewer_role, aud)
            return False
        if basename in policy_strategy:
            aud = normalize_audience_raw(audience_raw)
            return viewer_may_read_audience(viewer_role, aud)
        return False

    cfg_hr = load_hr_head_cross_access()
    merge_hr = cfg_hr.get("merge_hr_for_heads_of", [])
    allow_hr = frozenset(cfg_hr.get("allowed_cross_basenames", []))
    deny_hr = frozenset(cfg_hr.get("explicit_cross_deny_basenames", []))

    if (
        silo == "HR & Admin"
        and viewer_role
        and "Department Head" in viewer_role
        and viewer_active_department
        and viewer_active_department != "HR & Admin"
        and viewer_active_department in merge_hr
    ):
        if basename in deny_hr:
            return False
        if basename in allow_hr:
            aud = normalize_audience_raw(audience_raw)
            return viewer_may_read_audience(viewer_role, aud)
        return False

    cfg_it = load_it_head_cross_access()
    merge_it = cfg_it.get("merge_it_for_heads_of", [])
    allow_it = frozenset(cfg_it.get("allowed_cross_basenames", []))
    risk_it = frozenset(cfg_it.get("risk_only_extra_basenames", []))
    deny_it = frozenset(cfg_it.get("explicit_cross_deny_basenames", []))
    deny_sub_it = cfg_it.get("deny_substrings_in_basename_case_insensitive", [])
    if not isinstance(deny_sub_it, list):
        deny_sub_it = []

    if (
        silo == "IT & Digital"
        and viewer_role
        and "Department Head" in viewer_role
        and viewer_active_department
        and viewer_active_department != "IT & Digital"
        and viewer_active_department in merge_it
    ):
        if basename in deny_it:
            return False
        allowed_for_viewer = set(allow_it)
        if viewer_active_department == "Risk & Compliance":
            allowed_for_viewer = allowed_for_viewer | set(risk_it)
        if basename not in allowed_for_viewer:
            return False
        if _basename_matches_any_substring(basename, deny_sub_it):
            return False
        aud = normalize_audience_raw(audience_raw)
        return viewer_may_read_audience(viewer_role, aud)

    cfg_ops = load_ops_head_cross_access()
    merge_ops = cfg_ops.get("merge_ops_for_heads_of", [])
    allow_ops = frozenset(cfg_ops.get("allowed_cross_basenames", []))
    deny_ops_explicit = frozenset(cfg_ops.get("explicit_cross_deny_basenames", []))
    risk_ops_extra = frozenset(cfg_ops.get("risk_only_extra_basenames", []))
    risk_ops_sub = cfg_ops.get("risk_allow_substrings_in_basename_case_insensitive", [])
    if not isinstance(risk_ops_sub, list):
        risk_ops_sub = []
    hr_ops_sub = cfg_ops.get("hr_allow_substrings_in_basename_case_insensitive", [])
    if not isinstance(hr_ops_sub, list):
        hr_ops_sub = []
    deny_ops_sub = cfg_ops.get("deny_substrings_in_basename_case_insensitive", [])
    if not isinstance(deny_ops_sub, list):
        deny_ops_sub = []
    risk_exempt_deny = cfg_ops.get("risk_exempt_deny_substrings", [])
    if not isinstance(risk_exempt_deny, list):
        risk_exempt_deny = []

    if (
        silo == "Operations"
        and viewer_role
        and "Department Head" in viewer_role
        and viewer_active_department
        and viewer_active_department != "Operations"
        and viewer_active_department in merge_ops
    ):
        if basename in deny_ops_explicit:
            return False

        matched = basename in allow_ops
        if not matched and viewer_active_department == "HR & Admin":
            matched = _basename_matches_any_substring(basename, hr_ops_sub)
        if not matched and viewer_active_department == "Risk & Compliance":
            matched = basename in risk_ops_extra or _basename_matches_any_substring(
                basename, risk_ops_sub
            )
        if not matched:
            return False

        subs = list(deny_ops_sub)
        if viewer_active_department == "Risk & Compliance" and risk_exempt_deny:
            ex = {str(x) for x in risk_exempt_deny if isinstance(x, str) and x.strip()}
            subs = [s for s in subs if s not in ex]
        if _basename_matches_any_substring(basename, subs):
            return False

        aud = normalize_audience_raw(audience_raw)
        return viewer_may_read_audience(viewer_role, aud)

    cfg_rsk = load_risk_silo_cross_access()
    merge_rsk = cfg_rsk.get("merge_risk_silo_for_heads_of", [])
    allow_rsk = frozenset(cfg_rsk.get("allowed_cross_basenames", []))
    aml_it_ops = frozenset(cfg_rsk.get("it_and_operations_aml_extra_basenames", []))
    deny_rsk_explicit = frozenset(cfg_rsk.get("explicit_cross_deny_basenames", []))
    deny_rsk_sub = cfg_rsk.get("deny_substrings_in_basename_case_insensitive", [])
    if not isinstance(deny_rsk_sub, list):
        deny_rsk_sub = []
    auditee_raw = cfg_rsk.get("auditee_audit_report_basenames_by_department", {})
    if not isinstance(auditee_raw, dict):
        auditee_raw = {}

    if (
        silo == "Risk & Compliance"
        and viewer_role
        and "Department Head" in viewer_role
        and viewer_active_department
        and viewer_active_department != "Risk & Compliance"
        and viewer_active_department in merge_rsk
    ):
        if basename in deny_rsk_explicit:
            return False

        auditee_list = auditee_raw.get(viewer_active_department)
        if isinstance(auditee_list, list) and any(
            isinstance(x, str) and x == basename for x in auditee_list
        ):
            aud = normalize_audience_raw(audience_raw)
            return viewer_may_read_audience(viewer_role, aud)

        matched = basename in allow_rsk
        if (
            not matched
            and viewer_active_department in ("IT & Digital", "Operations")
        ):
            matched = basename in aml_it_ops
        if not matched:
            return False

        if _basename_matches_any_substring(basename, deny_rsk_sub):
            return False

        aud = normalize_audience_raw(audience_raw)
        return viewer_may_read_audience(viewer_role, aud)

    if viewer_role == "Operational Staff":
        denied = load_operational_staff_denylist().get(silo)
        if denied and basename in denied:
            return False
    aud = normalize_audience_raw(audience_raw)
    return viewer_may_read_audience(viewer_role, aud)


def list_authorized_vault_documents(
    vault_root: str,
    allowed_search_subsets,
    all_department_names: list[str],
    viewer_role: str | None = None,
    viewer_active_department: str | None = None,
) -> list[dict]:
    """
    Enumerate markdown docs the same way VaultWarden does, filtered by RBAC silos.
    allowed_search_subsets: \"ALL\" or list of department (folder) names.
    Optional viewer_role filters YAML audience: management vs everyone else.
    """
    if allowed_search_subsets == "ALL":
        scan_depts = list(all_department_names)
    else:
        scan_depts = [d for d in (allowed_search_subsets or []) if isinstance(d, str) and d.strip()]

    rows: list[dict] = []
    for dept in scan_depts:
        base = os.path.join(vault_root, dept)
        if not os.path.isdir(base):
            continue
        for root, _, files in os.walk(base):
            for fname in files:
                if not fname.endswith(".md") or fname.startswith("_"):
                    continue
                fpath = os.path.join(root, fname)
                relp = os.path.relpath(fpath, base).replace("\\", "/")
                try:
                    post = frontmatter.load(fpath)
                    aud = normalize_audience_raw(post.get("audience"))
                    if viewer_role is not None and not document_visible_to_viewer(
                        viewer_role,
                        dept,
                        os.path.basename(fpath),
                        post.get("audience"),
                        viewer_active_department,
                    ):
                        continue
                    summ = post.get("summary") or ""
                    if isinstance(summ, str) and len(summ) > 180:
                        summ = summ[:177] + "..."
                    rows.append(
                        {
                            "Silo": dept,
                            "Doc ID": str(post.get("doc_id", "—")),
                            "Title": str(post.get("title", fname.replace(".md", ""))),
                            "Category": str(post.get("category", "—")),
                            "Audience": "management" if aud == "management" else "all",
                            "File": relp,
                            "Summary": summ if isinstance(summ, str) else "",
                        }
                    )
                except (OSError, UnicodeDecodeError, ValueError, TypeError):
                    if viewer_role is not None and not document_visible_to_viewer(
                        viewer_role,
                        dept,
                        os.path.basename(fpath),
                        None,
                        viewer_active_department,
                    ):
                        continue
                    rows.append(
                        {
                            "Silo": dept,
                            "Doc ID": "—",
                            "Title": fname.replace(".md", ""),
                            "Category": "—",
                            "Audience": "all",
                            "File": relp,
                            "Summary": "",
                        }
                    )

    rows.sort(key=lambda r: (r["Silo"].lower(), str(r["Title"]).lower()))
    return rows


def safe_ai_call(func, *args, max_retries=3, **kwargs):
    """Safe wrapper for AI calls with exponential backoff and notification support."""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            err_msg = str(e).lower()
            retry_wait = (2 ** attempt) + 1
            
            if any(x in err_msg for x in ["429", "rate limit", "too many requests"]):
                print(f"⚠️ Rate limit hit. Retrying in {retry_wait}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(retry_wait)
            elif attempt < max_retries - 1:
                print(f"⚠️ API Error: {e}. Retrying in 1s...")
                time.sleep(1)
            else:
                msg = f"❌ FATAL API ERROR: {e}"
                print(msg)
                # Send critical notification
                notifier = NotificationManager()
                notifier.send_ops(f"🚨 SAG Critical Error:\n{e}")
                raise e
    return None

class NotificationManager:
    """Industrial-grade notification handler (LINE + Discord webhook)."""
    def __init__(self):
        self.token = CONFIG.get("LINE_NOTIFY_TOKEN")
        self.url = "https://notify-api.line.me/api/notify"
        self.discord_webhook = CONFIG.get("DISCORD_WEBHOOK_URL")

    def send_line(self, message):
        # Allow session token override
        try:
            import streamlit as st
            token = st.session_state.get("line_notify_token") or self.token
        except:
            token = self.token

        if not token or token == "INSERT_TOKEN_HERE":
            print(f"🔕 Notification skipped (No Token): {message}")
            return False
            
        try:
            import requests
            headers = {"Authorization": f"Bearer {token}"}
            payload = {"message": message}
            response = requests.post(self.url, headers=headers, data=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"⚠️ Failed to send LINE Notify: {e}")
            return False

    def send_discord(self, message):
        # Allow session override from Streamlit config page
        try:
            import streamlit as st
            webhook = st.session_state.get("discord_webhook_url") or self.discord_webhook
        except Exception:
            webhook = self.discord_webhook

        if not webhook:
            print(f"🔕 Discord skipped (No webhook): {message}")
            return False

        try:
            import requests
            payload = {"content": message}
            response = requests.post(webhook, json=payload, timeout=10)
            return 200 <= response.status_code < 300
        except Exception as e:
            print(f"⚠️ Failed to send Discord webhook: {e}")
            return False

    def send_ops(self, message):
        line_ok = self.send_line(message)
        discord_ok = self.send_discord(message)
        return line_ok or discord_ok

def extract_json(text):
    """Extracts JSON from a string."""
    match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
    return match.group(0) if match else text

class LLMInterface:
    """Central singleton-like accessor for the active LLM provider."""
    @staticmethod
    def get_client():
        from .LLMProviders import LLMFactory
        try:
            import streamlit as st
            provider = st.session_state.get("selected_provider", "Google")
            
            if provider == "Google":
                key = st.session_state.get("gemini_api_key") or CONFIG["GEMINI_API_KEY"]
                model = st.session_state.get("gemini_model") or CONFIG["GEMINI_MODEL"]
            elif provider == "OpenAI":
                key = st.session_state.get("openai_api_key") or CONFIG["OPENAI_API_KEY"]
                model = st.session_state.get("openai_model") or CONFIG.get("OPENAI_MODEL") or "gpt-4o"
            elif provider == "Anthropic":
                key = st.session_state.get("anthropic_api_key") or CONFIG["ANTHROPIC_API_KEY"]
                model = st.session_state.get("anthropic_model") or CONFIG.get("ANTHROPIC_MODEL") or "claude-3-5-sonnet-20240620"
            else:
                provider = "Google"
                key = CONFIG["GEMINI_API_KEY"]
                model = CONFIG["GEMINI_MODEL"]
            
            return LLMFactory.get_client(provider, key, model)
        except Exception:
            # CLI / scripts / threads: no Streamlit session — pick provider via SAG_PRIMARY_PROVIDER
            p = (os.getenv("SAG_PRIMARY_PROVIDER") or os.getenv("RAGD_PRIMARY_PROVIDER") or "google").strip().lower()
            if p in ("openai", "gpt"):
                key = CONFIG.get("OPENAI_API_KEY")
                model = os.getenv("OPENAI_MODEL") or os.getenv("SAG_OPENAI_MODEL") or os.getenv("RAGD_OPENAI_MODEL") or "gpt-4o"
                return LLMFactory.get_client("OpenAI", key, model)
            if p in ("anthropic", "claude"):
                key = CONFIG.get("ANTHROPIC_API_KEY")
                model = (
                    os.getenv("ANTHROPIC_MODEL")
                    or os.getenv("SAG_ANTHROPIC_MODEL")
                    or os.getenv("RAGD_ANTHROPIC_MODEL")
                    or "claude-3-5-sonnet-20240620"
                )
                return LLMFactory.get_client("Anthropic", key, model)
            key = CONFIG.get("GEMINI_API_KEY")
            model = CONFIG.get("GEMINI_MODEL") or "gemini-2.5-flash"
            return LLMFactory.get_client("Google", key, model)

def save_audit_event(data):
    """Saves an audit event (query + result + QC) to the log file."""
    path = CONFIG["AUDIT_LOG_PATH"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    events = []
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                events = json.load(f)
        except:
            events = []
            
    events.append(data)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(events, f, indent=4, ensure_ascii=False)
