import os
import re
import json
import time
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
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
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
                model = st.session_state.get("openai_model") or "gpt-4o"
            elif provider == "Anthropic":
                key = st.session_state.get("anthropic_api_key") or CONFIG["ANTHROPIC_API_KEY"]
                model = st.session_state.get("anthropic_model") or "claude-3-5-sonnet-20240620"
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
