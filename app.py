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
from core.Utils import (
    CONFIG,
    get_org_config,
    save_org_structure,
    save_audit_event,
    ROOT_PATH,
    LLMInterface,
    vault_doc_counts_for_departments,
    list_authorized_vault_documents,
    maybe_seed_demo_vault,
    merge_credit_cross_access_subset,
    merge_hr_cross_access_subset,
    merge_it_cross_access_subset,
    merge_ops_cross_access_subset,
    merge_risk_silo_cross_access_subset,
)
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


_GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]
_OPENAI_MODELS = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]
_ANTHROPIC_MODELS = ["claude-3-5-sonnet-20240620", "claude-3-5-haiku-20241022"]


def _write_config_dotenv():
    """Persist trial keys to local config/.env (gitignored)."""
    path = os.path.join(ROOT_PATH, "config", ".env")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _prov_map = {"Google": "google", "OpenAI": "openai", "Anthropic": "anthropic"}
    _rp = _prov_map.get(st.session_state.get("selected_provider", "Google"), "google")
    gm = (st.session_state.get("gemini_model") or CONFIG.get("GEMINI_MODEL") or "gemini-2.5-flash").strip()
    om = (st.session_state.get("openai_model") or CONFIG.get("OPENAI_MODEL") or "gpt-4o").strip()
    am = (st.session_state.get("anthropic_model") or CONFIG.get("ANTHROPIC_MODEL") or "claude-3-5-sonnet-20240620").strip()
    lines = [
        "# Written from SAG — do not commit.",
        f"RAGD_PRIMARY_PROVIDER={_rp}",
        f"GEMINI_MODEL={gm}",
        f"OPENAI_MODEL={om}",
        f"ANTHROPIC_MODEL={am}",
    ]
    g = (st.session_state.get("gemini_api_key") or "").strip()
    o = (st.session_state.get("openai_api_key") or "").strip()
    a = (st.session_state.get("anthropic_api_key") or "").strip()
    ln = (st.session_state.get("line_notify_token") or "").strip()
    dw = (st.session_state.get("discord_webhook_url") or "").strip()
    if g:
        lines.append(f"GEMINI_API_KEY={g}")
    if o:
        lines.append(f"OPENAI_API_KEY={o}")
    if a:
        lines.append(f"ANTHROPIC_API_KEY={a}")
    if ln:
        lines.append(f"LINE_NOTIFY_TOKEN={ln}")
    if dw:
        lines.append(f"DISCORD_WEBHOOK_URL={dw}")
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
st.set_page_config(page_title="SAG Industrial", page_icon="🏛️", layout="wide")

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
if "discord_webhook_url" not in st.session_state:
    st.session_state.discord_webhook_url = CONFIG.get("DISCORD_WEBHOOK_URL") or ""
if "gemini_model" not in st.session_state:
    st.session_state.gemini_model = CONFIG.get("GEMINI_MODEL") or "gemini-2.5-flash"
if "openai_model" not in st.session_state:
    st.session_state.openai_model = CONFIG.get("OPENAI_MODEL") or "gpt-4o"
if "anthropic_model" not in st.session_state:
    st.session_state.anthropic_model = CONFIG.get("ANTHROPIC_MODEL") or "claude-3-5-sonnet-20240620"

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


def _pick_model_select(options: list[str], state_attr: str, widget_key: str):
    cur = (st.session_state.get(state_attr) or "").strip()
    if cur not in options:
        cur = options[0]
        st.session_state[state_attr] = cur
    ix = options.index(cur)
    val = st.selectbox("Model", options, index=ix, key=widget_key)
    st.session_state[state_attr] = val


def render_api_and_model_form(*, compact: bool = False, key_prefix: str = "gate"):
    """Provider + model + API key (+ optional LINE). compact=True: gate before GURU."""
    provs = ["Google", "OpenAI", "Anthropic"]
    idx = provs.index(st.session_state.selected_provider) if st.session_state.selected_provider in provs else 0
    st.session_state.selected_provider = st.selectbox(
        "Provider", provs, index=idx, key=f"{key_prefix}_prov"
    )
    p = st.session_state.selected_provider

    c_m, c_k = st.columns([1, 1])
    with c_m:
        if p == "Google":
            _pick_model_select(_GEMINI_MODELS, "gemini_model", f"{key_prefix}_mm_g")
        elif p == "OpenAI":
            _pick_model_select(_OPENAI_MODELS, "openai_model", f"{key_prefix}_mm_o")
        else:
            _pick_model_select(_ANTHROPIC_MODELS, "anthropic_model", f"{key_prefix}_mm_a")
    with c_k:
        if p == "Google":
            st.session_state.gemini_api_key = st.text_input(
                "API key",
                value=st.session_state.gemini_api_key,
                type="password",
                key=f"{key_prefix}_k_g",
            )
        elif p == "OpenAI":
            st.session_state.openai_api_key = st.text_input(
                "API key",
                value=st.session_state.openai_api_key,
                type="password",
                key=f"{key_prefix}_k_o",
            )
        else:
            st.session_state.anthropic_api_key = st.text_input(
                "API key",
                value=st.session_state.anthropic_api_key,
                type="password",
                key=f"{key_prefix}_k_a",
            )

    if not compact:
        st.session_state.line_notify_token = st.text_input(
            "LINE Notify (optional)",
            value=st.session_state.line_notify_token,
            type="password",
            key="cfg_line",
        )
        st.session_state.discord_webhook_url = st.text_input(
            "Discord Webhook (optional)",
            value=st.session_state.discord_webhook_url,
            type="password",
            key="cfg_discord",
        )
        c_save, c_clear = st.columns(2)
        with c_save:
            if st.button("Save to config/.env", key="cfg_save_env"):
                _write_config_dotenv()
                st.success("Saved `config/.env`. Restart once to reload env at startup.")
        with c_clear:
            if st.button("Clear keys (this session)", key="cfg_clear"):
                st.session_state.gemini_api_key = ""
                st.session_state.openai_api_key = ""
                st.session_state.anthropic_api_key = ""
                st.session_state.line_notify_token = ""
                st.session_state.discord_webhook_url = ""
                get_services.clear()
                st.rerun()


if maybe_seed_demo_vault(ROOT_PATH, CONFIG["CLEANED_DATA_PATH"]):
    try:
        VaultWarden(CONFIG["CLEANED_DATA_PATH"]).audit_and_index()
        st.session_state["_demo_seed_notice"] = True
    except Exception as exc:
        print(f"[app] Demo vault index after auto-seed failed: {exc}")

services = get_services()

if "monitor_running" not in st.session_state:
    monitor = BackgroundMonitor()
    threading.Thread(target=monitor.start, daemon=True).start()
    st.session_state.monitor_running = True

if "current_result" not in st.session_state:
    st.session_state.current_result = None

# Sidebar Navigation
st.sidebar.title("Menu")
if st.session_state.pop("_demo_seed_notice", False):
    st.sidebar.success(
        "Setup: bundled **demo_knowledge/** was copied into **knowledge/** and indexed. "
        "Replace with your own vault anytime."
    )

PAGES = [
    "🔑 Start",
    "🧠 GURU Assistant",
    "📊 Audit Dashboard",
    "📽️ Showcase Clips",
    "🛠️ System Config",
]
_PAGES_LAYOUT_VERSION = 1
if st.session_state.get("_pages_layout_version", 0) < _PAGES_LAYOUT_VERSION:
    st.session_state.sidebar_main_nav = PAGES[0]
    st.session_state._pages_layout_version = _PAGES_LAYOUT_VERSION
if "sidebar_main_nav" not in st.session_state:
    st.session_state.sidebar_main_nav = PAGES[0]

page = st.sidebar.radio(
    "Go to",
    PAGES,
    key="sidebar_main_nav",
)
st.sidebar.divider()
st.sidebar.caption(f"Build {time.strftime('%Y%j')} · local-only")

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

if page == "🔑 Start":
    st.title("Start")
    render_api_and_model_form(compact=True, key_prefix="start")
    if st.button("Save to config/.env", key="start_save_env"):
        _write_config_dotenv()
        st.success("Saved.")
    if _provider_key_ready():
        st.success("Ready — open **🧠 GURU Assistant** in the sidebar.")

elif page == "🧠 GURU Assistant":
    if not _provider_key_ready():
        st.warning("Add your API key on **🔑 Start** first.")
        st.stop()

    st.title("🏛️ SAG: Financial Org Simulation")

    with st.expander("API & model", expanded=False):
        render_api_and_model_form(compact=True, key_prefix="guru_exp")
        if st.button("Save to config/.env", key="guru_exp_save"):
            _write_config_dotenv()
            st.success("Saved.")

    if st.session_state.get("guru_error"):
        st.warning(
            f"**Last request failed:**\n\n`{st.session_state['guru_error']}`\n\n"
            "Check your API key, quota, or network, then try again."
        )
    
    # Setup Checklist (Quick PnP View)
    with st.expander("🛠️ System Health & PnP Status", expanded=False):
        status_items = get_pnp_status()
        for label, ready in status_items:
            st.write(label)
    
    with st.expander("About this simulation", expanded=False):
        st.markdown(
            f"""
**Financial org simulation** — Zero-Vector-DB layout. Knowledge silos: **{', '.join(depts)}**.
            """
        )
    
    st.divider()

    doc_counts = vault_doc_counts_for_departments(CONFIG["CLEANED_DATA_PATH"], depts)
    total_docs = sum(doc_counts.values())
    st.caption(
        f"Vault `{CONFIG['CLEANED_DATA_PATH']}` · **{total_docs}** `.md` files across silos (pick a role below to see which ones you may use)."
    )

    # Identity: role drives RBAC; department picker only when role is silo-scoped (not CEO / ALL).
    col_p, col_d = st.columns(2)
    with col_p:
        selected_role = st.selectbox("👤 Identity Simulation (Select Position):", roles)

    role_info = next((r for r in org_config.get("roles", []) if r["role"] == selected_role), {})
    role_access = role_info.get("access", "SUBSET")
    selected_dept = None

    if role_access == "ALL":
        with col_d:
            st.markdown(f"📁 **Search scope:** **all silos** ({total_docs} docs)")
        allowed_search_subsets = "ALL"
        st.success(f"👑 {selected_role}: Master GURU Access (Full Org Visibility)")
    elif isinstance(role_access, list):
        _scope_docs = sum(doc_counts.get(d, 0) for d in role_access)
        allowed_search_subsets = role_access
        with col_d:
            if selected_role.startswith("CFO"):
                st.markdown(
                    f"📁 **CFO scope (finance & risk):** **{', '.join(role_access)}** · {_scope_docs} docs"
                )
            elif selected_role.startswith("CTO"):
                st.markdown(
                    f"📁 **CTO scope (tech & ops):** **{', '.join(role_access)}** · {_scope_docs} docs"
                )
            else:
                st.markdown(
                    f"📁 **Search scope:** **{', '.join(role_access)}** · {_scope_docs} docs"
                )
        if selected_role.startswith("CFO"):
            st.info(
                "💼 **CFO** — Finance & risk silos only (not org-wide like CEO)."
            )
        elif selected_role.startswith("CTO"):
            st.info(
                "💻 **CTO** — IT, operations & general silos only (not org-wide like CEO)."
            )
        else:
            st.warning(f"🛡️ {selected_role}: Multi-silo access ({', '.join(allowed_search_subsets)})")
    else:
        # SUBSET: scope = chosen silo; optional +General for VP (staff stays single silo).
        with col_d:
            selected_dept = st.selectbox(
                "📁 Active Department (Search Scope):",
                depts,
                format_func=lambda d: f"{d} ({doc_counts.get(d, 0)} docs)",
            )
        _inc_gen = bool(role_info.get("subset_include_general", False))
        if (
            _inc_gen
            and "General" in depts
            and selected_dept != "General"
        ):
            allowed_search_subsets = [selected_dept, "General"]
            _extra = doc_counts.get(selected_dept, 0) + doc_counts.get("General", 0)
            st.info(
                f"🏢 **{selected_role}** — silos **{selected_dept}** + **General** "
                f"(policies/HQ context) · ~{_extra} docs"
            )
        else:
            allowed_search_subsets = [selected_dept]
            _n = doc_counts.get(selected_dept, 0)
            if selected_role == "Operational Staff":
                st.info(f"📋 **Operational Staff** — **{selected_dept}** silo only (~{_n} docs).")
            else:
                st.info(f"📁 **{selected_role}** — **{selected_dept}** (~{_n} docs)")

    allowed_search_subsets = merge_credit_cross_access_subset(
        allowed_search_subsets, selected_role, selected_dept
    )
    allowed_search_subsets = merge_hr_cross_access_subset(
        allowed_search_subsets, selected_role, selected_dept
    )
    allowed_search_subsets = merge_it_cross_access_subset(
        allowed_search_subsets, selected_role, selected_dept
    )
    allowed_search_subsets = merge_ops_cross_access_subset(
        allowed_search_subsets, selected_role, selected_dept
    )
    allowed_search_subsets = merge_risk_silo_cross_access_subset(
        allowed_search_subsets, selected_role, selected_dept
    )

    auth_doc_rows = list_authorized_vault_documents(
        CONFIG["CLEANED_DATA_PATH"],
        allowed_search_subsets,
        depts,
        viewer_role=selected_role,
        viewer_active_department=selected_dept,
    )
    st.markdown("##### Documents available to this identity (for drafting questions)")
    st.caption(
        "Preview matches search/GURU. **Department Head (non-Credit):** added **Credit** silo — "
        "`config/credit_head_cross_access.json`. **Risk** head: near–full Credit. "
        "**Department Head (non-HR):** added **HR & Admin** — "
        "`config/hr_head_cross_access.json`. **Department Head (non-IT):** added **IT & Digital** — "
        "`config/it_head_cross_access.json`. **Department Head (non-Operations):** added **Operations** — "
        "`config/ops_head_cross_access.json`. **Department Head (non-Risk):** added **Risk & Compliance** — "
        "`config/risk_silo_cross_access.json`. Optional YAML **audience: management**; column **Audience**."
    )
    if auth_doc_rows:
        st.dataframe(
            pd.DataFrame(auth_doc_rows),
            hide_index=True,
            use_container_width=True,
            height=min(420, 120 + min(len(auth_doc_rows), 12) * 36),
        )
    else:
        st.warning(
            "No `.md` documents under your authorized silos. "
            "Place files under `knowledge/<Department name>/` so folder names match **org_structure.json**, "
            "or run **Rebuild vault index** from System Config."
        )

    with st.expander("Example questions (copy into chat)", expanded=False):
        st.markdown(
            """
- What are the main policies or rules in **this** department’s vault?
- Summarize anything related to **[topic]** from my allowed silos.
- Are there deadlines, limits, or exceptions I should know?
            """.strip()
        )

    # Expert Query Interface
    st.divider()
    query = st.chat_input(f"Enter your query as {selected_role}...")
    
    if query:
        with st.status("🚀 GURU is scouting the authorized silos...", expanded=True) as status:
            try:
                st.write("🔍 Identifying Swarm Keywords...")
                time.sleep(1)
                st.write("🤖 Dispatches Parallel Bots...")
                result = services["orchestrator"].handle_request(
                    query,
                    allowed_search_subsets,
                    selected_role,
                    viewer_active_department=selected_dept,
                )
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
                st.error(f"**Request failed:** {e}")

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

    with st.expander("API & model (+ LINE optional)", expanded=False):
        render_api_and_model_form(compact=False, key_prefix="syscfg")

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
        "Scans the knowledge vault and writes `_SEARCH_CACHE.json` and `_MASTER_INDEX.md` for faster deterministic search."
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
        "Edit tables, then save to `config/org_structure.json`. Department **names** should match subfolders under `knowledge/`."
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
