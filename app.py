import streamlit as st
import os
import time
import ast
import json
import pandas as pd
from core.Refinery import DataRefinery
from core.Orchestrator import RAGOrchestrator
from core.Exporter import FileExporter
from core.Monitor import BackgroundMonitor
from core.VaultWarden import VaultWarden
from core.AuditJudge import AuditJudge
from core.Utils import CONFIG, get_org_config, save_org_structure, save_audit_event, ROOT_PATH, LLMInterface
import threading


def _df_to_json_safe_records(df: pd.DataFrame) -> list:
    """Turn data_editor output into JSON-safe records (NaN -> None, fix stringified lists)."""
    if df is None or df.empty:
        return []
    obj = df.astype(object).where(pd.notnull(df), None)
    rows = obj.to_dict(orient="records")
    for row in rows:
        for key in ("keywords", "access"):
            val = row.get(key)
            if isinstance(val, str) and val.strip().startswith("["):
                try:
                    row[key] = ast.literal_eval(val)
                except (SyntaxError, ValueError, TypeError, OSError):
                    pass
    return rows


def _write_config_dotenv():
    """Persist trial keys to local config/.env (gitignored)."""
    path = os.path.join(ROOT_PATH, "config", ".env")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _prov_map = {"Google": "google", "OpenAI": "openai", "Anthropic": "anthropic"}
    _rp = _prov_map.get(st.session_state.get("selected_provider", "Google"), "google")
    lines = [
        "# Written from RAG-Destroyer System Config — do not commit.",
        f"RAGD_PRIMARY_PROVIDER={_rp}",
        f"GEMINI_MODEL={CONFIG.get('GEMINI_MODEL') or 'gemini-2.5-flash'}",
    ]
    g = (st.session_state.get("gemini_api_key") or "").strip()
    o = (st.session_state.get("openai_api_key") or "").strip()
    a = (st.session_state.get("anthropic_api_key") or "").strip()
    ln = (st.session_state.get("line_notify_token") or "").strip()
    if g:
        lines.append(f"GEMINI_API_KEY={g}")
    if o:
        lines.append(f"OPENAI_API_KEY={o}")
    if a:
        lines.append(f"ANTHROPIC_API_KEY={a}")
    if ln:
        lines.append(f"LINE_NOTIFY_TOKEN={ln}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def _provider_key_ready():
    p = st.session_state.get("selected_provider", "Google")
    if p == "Google":
        return bool((st.session_state.get("gemini_api_key") or "").strip())
    if p == "OpenAI":
        return bool((st.session_state.get("openai_api_key") or "").strip())
    if p == "Anthropic":
        return bool((st.session_state.get("anthropic_api_key") or "").strip())
    return False


# Page Config
st.set_page_config(page_title="RAG-Destroyer Industrial", page_icon="🏛️", layout="wide")

# Persistent Session Defaults for Multi-LLM
if "selected_provider" not in st.session_state:
    st.session_state.selected_provider = "Google"
if "gemini_api_key" not in st.session_state:
    st.session_state.gemini_api_key = CONFIG.get("GEMINI_API_KEY", "")
if "openai_api_key" not in st.session_state:
    st.session_state.openai_api_key = CONFIG.get("OPENAI_API_KEY", "")
if "anthropic_api_key" not in st.session_state:
    st.session_state.anthropic_api_key = CONFIG.get("ANTHROPIC_API_KEY", "")
if "line_notify_token" not in st.session_state:
    st.session_state.line_notify_token = CONFIG.get("LINE_NOTIFY_TOKEN") or ""

# Initialize Core Services
@st.cache_resource
def get_services():
    return {
        "orchestrator": RAGOrchestrator(),
        "refinery": DataRefinery(),
        "exporter": FileExporter(),
        "judge": AuditJudge(),
        "warden": VaultWarden()
    }

services = get_services()

if "monitor_running" not in st.session_state:
    monitor = BackgroundMonitor()
    threading.Thread(target=monitor.start, daemon=True).start()
    st.session_state.monitor_running = True

if "current_result" not in st.session_state:
    st.session_state.current_result = None

# Sidebar Navigation
st.sidebar.title("🎮 Command Center")
page = st.sidebar.radio("Navigate to:", ["🧠 GURU Assistant", "📊 Audit Dashboard", "📽️ Showcase Clips", "🛠️ System Config"])

# Load Org Data
org_config = get_org_config()
depts = [d["name"] for d in org_config.get("departments", [])]
roles = [r["role"] for r in org_config.get("roles", [] )]

# Helper for PnP Status Checklist
def get_pnp_status():
    status = []
    api_ready = _provider_key_ready()
    status.append(("✅ API Keys Linked" if api_ready else "❌ API Keys Missing", api_ready))
    
    # Storage Check
    raw_exists = os.path.exists(CONFIG["RAW_DATA_PATH"])
    status.append(("✅ Raw Storage Pipeline Active" if raw_exists else "⚠️ Raw Folder Missing", raw_exists))
    
    vault_exists = os.path.exists(CONFIG["CLEANED_DATA_PATH"])
    status.append(("✅ Knowledge Vault Active" if vault_exists else "❌ Vault Missing", vault_exists))
    
    return status

if page == "🧠 GURU Assistant":
    st.title("🏛️ RAG-Destroyer: Financial Org Simulation")

    if not _provider_key_ready():
        st.info(
            "**ผู้ทดลองใช้ / Trial:** เปิดแถบซ้ายไปที่ **🛠️ System Config** แล้วเลือกผู้ให้บริการ AI "
            "และวาง **API key ของคุณเอง** (ไม่ถูกอัปโหลดไป GitHub). "
            "**Trial:** Use **🛠️ System Config** in the sidebar to pick a provider and paste **your own API key**."
        )

    if st.session_state.get("guru_error"):
        st.warning(
            f"ครั้งล่าสุดล้มเหลว / Last run failed:\n\n`{st.session_state['guru_error']}`\n\n"
            "ตรวจ API key, โควต้า, หรือเครือข่าย แล้วลองถามใหม่ / Check API key, quota, or network, then ask again."
        )
    
    # Setup Checklist (Quick PnP View)
    with st.expander("🛠️ System Health & PnP Status", expanded=False):
        status_items = get_pnp_status()
        for label, ready in status_items:
            st.write(label)
    
    st.info(f"""
    **🏢 Financial Organization Simulation (Digital Banking)**
    This system uses the **Zero-Vector-DB** architecture to manage knowledge across departmental silos.
    Knowledge is partitioned into {len(depts)} Primary Silos:
    👉 **{', '.join(depts)}**
    """)
    
    st.divider()

    # Dropdowns for Identity Simulation
    col_p, col_d = st.columns(2)
    with col_p:
        selected_role = st.selectbox("👤 Identity Simulation (Select Position):", roles)
    with col_d:
        selected_dept = st.selectbox("📁 Active Department (Search Scope):", depts)

    # Security Context Logic
    role_info = next((r for r in org_config.get("roles", []) if r["role"] == selected_role), {})
    role_access = role_info.get("access", "SUBSET")
    
    if role_access == "ALL":
        allowed_search_subsets = "ALL"
        st.success(f"👑 {selected_role}: Master GURU Access (Full Org Visibility)")
    elif isinstance(role_access, list):
        allowed_search_subsets = role_access
        st.warning(f"🛡️ {selected_role}: Multi-Silo Access ({', '.join(allowed_search_subsets)})")
    else:
        allowed_search_subsets = [selected_dept]
        st.info(f"📁 Role: {selected_role} | Silo: {selected_dept} (Restricted Access)")

    # Expert Query Interface
    st.divider()
    query = st.chat_input(f"Enter your query as {selected_role}...")
    
    if query:
        with st.status("🚀 GURU is scouting the authorized silos...", expanded=True) as status:
            try:
                st.write("🔍 Identifying Swarm Keywords...")
                time.sleep(1)
                st.write("🤖 Dispatches Parallel Bots...")
                result = services["orchestrator"].handle_request(query, allowed_search_subsets)
                st.session_state.last_query = query

                st.write("⚖️ Running AI QC Audit (Dual 5+5 Scoring)...")
                qc_result = services["judge"].evaluate(query, result["sources"], result["answer"])
                result["qc"] = qc_result
                st.session_state.current_result = result
                st.session_state.pop("guru_error", None)
                status.update(label="✅ Synthesis Complete!", state="complete", expanded=False)
            except Exception as e:
                st.session_state.current_result = None
                st.session_state["guru_error"] = str(e)
                status.update(label="❌ Request failed", state="error", expanded=True)
                st.error(f"**ไม่สามารถประมวลผลคำขอได้ / Request failed:** {e}")

    # Display Result
    if st.session_state.current_result:
        res = st.session_state.current_result
        st.chat_message("user").write(st.session_state.get("last_query", "Previous Request"))
        with st.chat_message("assistant"):
            st.write(res['answer'])
            
            # QC Dual Badge
            qc = res.get('qc', {})
            total_score = qc.get('qc_score', 0)
            acc_score = qc.get('accuracy_score', 0)
            lang_score = qc.get('language_score', 0)
            
            color = "green" if total_score >= 8 else "orange" if total_score >= 4 else "red"
            st.markdown(f"### **QC Audit Status:** :{color}[Total Score {total_score}/10]")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Context Accuracy", f"{acc_score}/5")
            c2.metric("Language & Tone", f"{lang_score}/5")
            c3.metric("Tone Grade", qc.get('tone_grade', 'N/A'))
            
            if qc.get('critique'):
                st.caption(f"**AI Judge Critique:** {qc['critique']}")
            
            with st.expander("📚 View Authorized Sources"):
                for doc in res['sources']:
                    st.info(f"**{doc['title']}** (ID: {doc.get('doc_id')}) - Relevance: {doc['relevance']}")

            # Feedback Form
            st.divider()
            st.subheader("📝 Accuracy Feedback (Demo Improvement)")
            f_col1, f_col2 = st.columns([1, 2])
            with f_col1:
                rating = st.slider("Rate Accuracy", 1, 10, 10)
            with f_col2:
                comment = st.text_input("Comments for Code Improvement")
            
            if st.button("💾 Save to Audit Trail"):
                audit_data = {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "role": selected_role,
                    "provider": st.session_state.selected_provider,
                    "query": st.session_state.get("last_query", "N/A"),
                    "answer": res['answer'],
                    "user_rating": rating,
                    "user_comment": comment,
                    "qc_score": total_score,
                    "acc_score": acc_score,
                    "lang_score": lang_score
                }
                save_audit_event(audit_data)
                st.success("Audit data saved locally for demo analysis!")

elif page == "📊 Audit Dashboard":
    st.title("📊 Industrial Audit Dashboard")
    st.markdown("### Real-World Multi-Role Performance Audit")
    path = CONFIG["AUDIT_LOG_PATH"]
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        df = pd.DataFrame(data)
        st.dataframe(df, width=None) # Corrected use_container_width to None
        
        st.divider()
        st.subheader("📈 Quality Analytics")
        if not df.empty:
            avg_qc = df["qc_score"].mean()
            st.progress(avg_qc/10, text=f"Average QC Score: {avg_qc:.2f}/10")
    else:
        st.warning("No audit logs found.")

elif page == "📽️ Showcase Clips":
    st.title("📽️ Technological Showcase")
    st.markdown("### Real-World Operations & Stress-Test Evidence")
    
    showcase_dir = os.path.join(ROOT_PATH, "assets", "showcase")
    
    if os.path.exists(showcase_dir):
        col1, col2 = st.columns(2)
        
        clips = sorted([f for f in os.listdir(showcase_dir) if f.endswith(".webp")])
        
        for i, clip in enumerate(clips):
            target_col = col1 if i % 2 == 0 else col2
            with target_col:
                title = clip.replace(".webp", "").replace("_", " ").split(" ", 1)[-1]
                st.subheader(f"Step {i+1}: {title}")
                st.image(os.path.join(showcase_dir, clip), use_column_width=True)
                st.caption(f"Captured during Industrial Stress Test - GURU in the box.")
    else:
        st.warning("Real showcase assets not found. Please run the Audit test first.")

elif page == "🛠️ System Config":
    st.title("🛠️ System Configuration")

    st.markdown(
        """
### ผู้ทดลองใช้ (Bring your own key)
โคลนโปรเจกต์แล้วรัน `streamlit run app.py` — **ไม่ต้องมี `config/.env` ก่อน**  
ใส่ API key **ของคุณ**ด้านล่างเพื่อทดลอง GURU, Refinery และ QC บนเครื่องคุณเท่านั้น  
ค่า key เก็บใน **session ของ Streamlit** จนกว่าจะปิดแท็บ/รีสตาร์ทแอป (หรือกดบันทึกลงไฟล์ด้านล่าง)

### Trial downloaders (BYOK)
Clone, run `streamlit run app.py` — **no `config/.env` required** to start.  
Paste **your** provider API key below to try GURU, Refinery, and QC locally. Keys stay in this **Streamlit session** until you close the tab or restart (optional: save to a local file below).
        """
    )

    # 1. Multi-LLM Setup
    st.header("🔑 API credentials (your keys)")
    st.session_state.selected_provider = st.selectbox(
        "Primary AI provider",
        ["Google", "OpenAI", "Anthropic"],
        index=["Google", "OpenAI", "Anthropic"].index(st.session_state.selected_provider),
        help="เลือกให้ตรงกับ key ที่คุณจะวาง / Must match the key you paste.",
    )

    col1, col2 = st.columns(2)
    with col1:
        st.session_state.gemini_api_key = st.text_input(
            "Google Gemini API key",
            value=st.session_state.gemini_api_key,
            type="password",
            help="https://aistudio.google.com/apikey",
        )
        st.session_state.openai_api_key = st.text_input(
            "OpenAI API key",
            value=st.session_state.openai_api_key,
            type="password",
            help="https://platform.openai.com/api-keys",
        )
    with col2:
        st.session_state.anthropic_api_key = st.text_input(
            "Anthropic API key",
            value=st.session_state.anthropic_api_key,
            type="password",
            help="https://console.anthropic.com/",
        )
        st.session_state.line_notify_token = st.text_input(
            "LINE Notify token (optional)",
            value=st.session_state.line_notify_token,
            type="password",
        )

    st.caption(
        "คีย์ไม่ถูกส่งไป GitHub — รันแบบ local เท่านั้น / Keys are not sent to GitHub; this app runs locally."
    )

    c_save, c_clear = st.columns(2)
    with c_save:
        if st.button("💾 Save keys to config/.env on this PC", help="Creates `config/.env` (gitignored). Convenient for next run."):
            _write_config_dotenv()
            st.success("Saved to `config/.env`. Restart the app once if you want `python-dotenv` to reload it at import time.")
    with c_clear:
        if st.button("🗑️ Clear keys from this session"):
            st.session_state.gemini_api_key = ""
            st.session_state.openai_api_key = ""
            st.session_state.anthropic_api_key = ""
            st.session_state.line_notify_token = ""
            get_services.clear()
            st.rerun()

    st.caption("แม่แบบตัวแปร: `config/.env.example` — คัดลอกเป็น `config/.env` แล้วแก้ได้ด้วยมือ / Template: `config/.env.example`.")

    # 2. Knowledge Valve (Path Settings)
    st.divider()
    st.header("📁 Knowledge paths (optional)")
    raw_path = st.text_input("Raw data folder", value=CONFIG["RAW_DATA_PATH"])
    vault_path = st.text_input("Knowledge vault folder", value=CONFIG["CLEANED_DATA_PATH"])

    if st.button("🔧 Apply storage paths"):
        CONFIG["RAW_DATA_PATH"] = raw_path.strip()
        CONFIG["CLEANED_DATA_PATH"] = vault_path.strip()
        get_services.clear()
        st.success("Paths updated. Orchestrator & refinery reloaded. Restart Streamlit if the background file watcher should use the new raw folder.")
        st.rerun()

    # 2b. Vault index (search cache)
    st.divider()
    st.header("📇 Vault index & search cache")
    st.caption(
        "สแกนโฟลเดอร์ knowledge แล้วสร้าง `_SEARCH_CACHE.json` และ `_MASTER_INDEX.md` "
        "ให้การค้นหาเร็วขึ้น / Scans the knowledge vault for fast deterministic search."
    )
    if st.button("🔁 Rebuild vault index & search cache", type="primary"):
        with st.spinner("Indexing markdown vault..."):
            services["warden"].audit_and_index()
        get_services.clear()
        st.success("Index updated. Orchestrator reloaded.")
        st.rerun()

    # 3. Org Structure Data
    st.divider()
    st.header("🏢 Organization structure")
    st.caption(
        "แก้แล้วกดบันทึกลง `config/org_structure.json` — ชื่อแผนกควรตรงกับโฟลเดอร์ใต้ `knowledge/` "
        "/ Edit then save; department names should match folders under `knowledge/`."
    )
    config_tab1, config_tab2 = st.tabs(["📁 Departments", "👤 Roles"])
    with config_tab1:
        dept_df = st.data_editor(
            pd.DataFrame(org_config.get("departments", [])),
            num_rows="dynamic",
            use_container_width=True,
            key="org_edit_departments",
        )
    with config_tab2:
        role_df = st.data_editor(
            pd.DataFrame(org_config.get("roles", [])),
            num_rows="dynamic",
            use_container_width=True,
            key="org_edit_roles",
        )
    if st.button("💾 Save organization to config/org_structure.json"):
        merged = dict(org_config)
        merged["departments"] = _df_to_json_safe_records(dept_df)
        merged["roles"] = _df_to_json_safe_records(role_df)
        save_org_structure(merged)
        st.success("Saved `config/org_structure.json`. Refreshing…")
        st.rerun()

# Footer
st.sidebar.divider()
st.sidebar.caption(f"RAG-Destroyer Industrial | Build: {time.strftime('%Y%j')}")
st.sidebar.caption("Privacy: Local Vault & API Keys are NOT shared with GitHub.")

# PnP: remind trial users to set the key for the selected provider
if not _provider_key_ready():
    st.sidebar.warning("⚠️ API key: open **🛠️ System Config** and paste your key for the selected provider.")
