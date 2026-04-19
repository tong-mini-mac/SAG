import os
import re
import json
import time
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


def list_authorized_vault_documents(
    vault_root: str,
    allowed_search_subsets,
    all_department_names: list[str],
    viewer_role: str | None = None,
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
                    if viewer_role is not None and not viewer_may_read_audience(viewer_role, aud):
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
                notifier.send_line(f"🚨 RAG-Destroyer Critical Error:\n{e}")
                raise e
    return None

class NotificationManager:
    """Industrial-grade notification handler (LINE Notify)."""
    def __init__(self):
        self.token = CONFIG.get("LINE_NOTIFY_TOKEN")
        self.url = "https://notify-api.line.me/api/notify"

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
            # CLI / scripts / threads: no Streamlit session — pick provider via RAGD_PRIMARY_PROVIDER
            p = (os.getenv("RAGD_PRIMARY_PROVIDER") or "google").strip().lower()
            if p in ("openai", "gpt"):
                key = CONFIG.get("OPENAI_API_KEY")
                model = os.getenv("OPENAI_MODEL") or os.getenv("RAGD_OPENAI_MODEL") or "gpt-4o"
                return LLMFactory.get_client("OpenAI", key, model)
            if p in ("anthropic", "claude"):
                key = CONFIG.get("ANTHROPIC_API_KEY")
                model = (
                    os.getenv("ANTHROPIC_MODEL")
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
