<div align="center">
  <img src="docs/img/architecture.png" width="100%" alt="SAG: Obsidian Graph x Subset Architecture">
  <h1>🏛️ SAG (Subset-Augmented Generation): The Zero-Vector-DB Architecture</h1>
  <p><b>Deterministic Knowledge Retrieval for the LLM OS Era</b></p>
  <p><i>Repository documentation is maintained in English.</i></p>
</div>

<br>

> *"An LLM is the CPU of an emerging operating system."* — **Andrej Karpathy**

### 💡 Inspiration: Standing on the Shoulders of Giants
This project exists because of **Andrej Karpathy's** brilliant vision of the "LLM OS". He proposed that an LLM shouldn't just be a chatbot, but the core processor of a new operating system—capable of reading files, managing memory, and respecting user permissions natively.

While the AI industry rushed to dump enterprise data into complex, multi-million dollar, black-box Vector Databases, they forgot the fundamental requirement of any Operating System: **A deterministic, permission-aware File System.**

**SAG (Subset-Augmented Generation)** is my practical implementation of that missing layer.

---

## 🧪 Proving the Theory: A Manifesto for GURU in the Box
**This project was built to prove a theory, not to be sold as a commercial product.**

The goal of **SAG (Subset-Augmented Generation)** is to serve as a **Proof of Concept (PoC)** to demonstrate a singular truth: *A deterministic, Zero-Vector-DB architecture using the "Subset Theory" can eliminate data leakage and hallucination in high-security environments.*

I am not looking for profit or a commercial software license. My only objective was to prove that this architectural approach—the anti-vector-overkill philosophy described above—is the correct foundation for enterprise-grade AI security.

**The theory is proven. The foundation is here.**

This repository is provided as an open-source foundation. You are free to take this architecture, adapt it, integrate it with your enterprise's complex RBAC (Active Directory, OAuth, etc.), and scale it for your own needs.

*The framework is public. The proof is undeniable. The implementation is now yours.*

---

## 💣 The Vector DB Delusion
The Enterprise AI industry is lying to you. We are forcing semantic search into enterprise environments where **precision, access control (RBAC), and auditability** matter more than "finding similar meanings."

Vector DBs for internal documents are a nightmare:
1. **They hallucinate (Semantic Drift):** Searching for "Maternity Leave" might pull "Sick Leave" because the math thinks they are close.
2. **RBAC is an afterthought:** Telling a vector space "Don't let the intern see the CEO's salary" is computationally expensive and flawed.
3. **They are overpriced:** You are paying cloud providers for something your local file system can do better.

## 🧠 Enter "The Subset Theory"
I killed the Vector DB and replaced it with **The Subset Theory**.

Instead of converting your company's knowledge into billions of unreadable numbers, we flip the architecture:

1. **Deterministic Scouting:** We use high-speed, multi-threaded worker bots to aggressively filter and extract the exact **"Subset"** of relevant data using deterministic metadata, tags, and keyword swarms over an Obsidian (Markdown) vault.
2. **The LMM as a Synthesizer:** Once the perfect "Subset" is isolated, we feed *only* that pristine data to the Large Multimodal Model (LMM). The LMM's only job is to reason and synthesize the final answer.
3. **Zero-Trust by Default:** Because the search happens at the OS file-system level, Role-Based Access Control (RBAC) is native. If a user doesn't have OS-level clearance for a folder, the worker bots simply don't see it. Zero data leakage.

## 🛡️ The "Anti-Roast" Shield
*Before you say it in the Hacker News comments: Yes, I know I just reinvented Keyword Search and Metadata Filtering. And that is EXACTLY the point.*

We got so obsessed with shiny Vector DBs and complex embeddings that we forgot basic software engineering. For 90% of enterprise data, simple deterministic search + LLM reasoning is faster, cheaper, and 100x easier to secure than a black-box vector space. Sometimes, the "dumb" way is the most elegant architecture.

## 🚀 Features
- **Zero Vector DB:** $0 cost, 0 maintenance.
- **100% Native RBAC:** Inherits your organizational silo permissions automatically.
- **Zero Hallucination Retrieval:** If the deterministic search doesn't find it, it doesn't get synthesized.
- **Multi-threaded Speed:** Parallel worker agents (optimized swarm) scout the vault in milliseconds.
- **Industrial Resilience:** Integrated safety cut (circuit breaker) and industrial operational watchdog.
- **Demo Audit Layer:** AI-on-AI QC judging and performance dashboard (built for continuous improvement).
- **Layered cross-silo access for VPs:** Department Heads can receive *merged* silo search scope with per-file policies (whitelist / deny / substring rules) — see **§ Organization model** below.
- **Identity-first question drafting:** GURU shows a role-scoped document preview table before prompting, so users can draft questions from only the documents they are authorized to see.
- **Ops alert relay:** Optional LINE and Discord webhook notifications for critical runtime/API failures.

---

## 🛡️ Data privacy, `knowledge/`, and what belongs on GitHub

> [!WARNING]
> **Public GitHub = application code only.** Treat your Markdown vault as **data**, not as part of the public template.

| Location | Typical contents | On public GitHub? |
| :--- | :--- | :--- |
| Repo root (`app.py`, `core/`, `docs/`, Docker files, `config/.env.example`) | Orchestration, UI, docs | **Yes** — safe to push |
| `config/.env` | API keys, tokens | **Never** — gitignored; copy from `config/.env.example` |
| `knowledge/` | Markdown silos ("vault"), RBAC-sensitive text | **No** (default) — `.gitignore` keeps it local / on your machine only |
| `raw_data/` | Drop zone for ingestion | **No** — gitignored |
| `logs/` | Runtime / audit JSON | **No** — gitignored |
| `.obsidian/` | Obsidian workspace metadata | **No** — gitignored |

**Why not push `knowledge/` to a public repo?**  
Once pushed, content is **copied forever** across forks, clones, and search indexes. Enterprise playbooks, customer names, or policy drafts do not belong next to open-source code unless you have explicitly cleared legal + security review.

**If you truly need Git-backed vaults:**

- **Private repository** (org-only) + branch protections — still treat as sensitive; rotate anything that ever leaked to a public remote by mistake.
- **Separate private repo** for `knowledge/` only (or Git submodule) so the public SAG repo stays code-only.
- **No Git at all for vault:** keep `knowledge/` on disk, NAS, S3, or Google Drive — the **Docker Compose** setup bind-mounts `./knowledge` and `./raw_data` from the host; the container never required the vault to live inside the image.

**Google Drive / local paths:** Never commit machine-specific absolute paths or synced folders that contain private files.

---

## 👥 Getting the code (evaluators, testers, forks)

You can download and run this project **without being the maintainer**.

| Method | What to do |
| :--- | :--- |
| **Git clone** | `git clone https://github.com/tong-mini-mac/SAG.git` then follow **§ Quick start** below. |
| **ZIP** | On GitHub: **Code → Download ZIP**, extract, then open a terminal in that folder. |

### What testers and evaluators should know

Tell anyone trying the demo the following:

1. **There is no `knowledge/` vault inside the repo.** It is **gitignored** on purpose (**privacy policy** — see **Data Privacy & GitHub Policy** above). After `git clone` or unzipping, **you must supply Markdown yourself**: build **`knowledge/<Department>/`** to match **`config/org_structure.json`**, **or** copy from the repo’s **`demo_knowledge/`** into **`knowledge/`** as described in this README (**same folder names as department silos**).

2. **Automatic demo seed (optional):** If **`knowledge/`** has **no** `.md` files yet and **`demo_knowledge/`** exists next to the app, **`maybe_seed_demo_vault`** (`core/Utils.py`) may copy **`demo_knowledge/` → `knowledge/`** on startup. Create **`knowledge/.no_auto_demo`** to disable that behaviour.

3. **API keys (BYOK):** Bring **your own** LLM credentials. Enter them in the Streamlit UI or **`config/.env`** (see **Quick start §2** and **`config/.env.example`**).

4. **Repository access:** If this GitHub repo is **public**, anyone can clone or download the ZIP. If it is **private**, only **invited users** or accounts **granted access** can clone or pull.

**In short:** testers get the **code** via **`git clone`** or **ZIP**. Whether that works **without extra GitHub login** depends on **public vs private**. They always need to **prepare a vault under `knowledge/`** (manually, from **`demo_knowledge/`**, or via **auto-seed**) and **their own API key**.

---

## 🏢 Organization model: silos, roles (CEO → Operational Staff), and cross-merge

The **subset** enforced at query time uses `config/org_structure.json`, `core/Utils.py` (`document_visible_to_viewer`), YAML `audience` in front matter (e.g. `management`), and optional config files listed below.

### Department silos (folder names under `knowledge/`)

These must match the `name` field for each department in **`config/org_structure.json`**.

| Silo | Code | Focus |
|------|------|--------|
| **General** | GEN | Company-wide / HQ policies |
| **Credit & Loans** | CRL | Lending |
| **Operations** | OPS | Branches / operations |
| **IT & Digital** | ITD | Technology & digital |
| **HR & Admin** | HRA | HR & admin |
| **Risk & Compliance** | RSK | Risk & compliance |

### Role → search scope (vault)

| Role | Search scope | Notes |
|------|----------------|-------|
| **CEO** | **ALL** silos | Full vault; still respects YAML `audience` when set. |
| **CFO** | **Credit & Loans**, **Risk & Compliance**, **General** | Fixed list in `org_structure.json`. |
| **CTO** | **IT & Digital**, **Operations**, **General** | Fixed list in `org_structure.json`. |
| **Department Head (VP)** | **Selected department + General** (`subset_include_general: true`) **plus merged silos** (see below) **and** per-file filtering. |
| **Operational Staff** | **Selected department only** (no General by default) | Extra per-department **denylist** in `config/operational_staff_vault_denylist.json`. |

Operational Staff (and roles with a single silo) **do not** see `audience: management` documents unless the role is treated as management in code.

### Cross-silo merge (Department Head only)

For **Department Head (VP)** the app expands the allowed folder list **after** `[department, General]` using, **in order**:

1. `merge_credit_cross_access_subset` → `config/credit_head_cross_access.json`
2. `merge_hr_cross_access_subset` → `config/hr_head_cross_access.json`
3. `merge_it_cross_access_subset` → `config/it_head_cross_access.json`
4. `merge_ops_cross_access_subset` → `config/ops_head_cross_access.json`
5. `merge_risk_silo_cross_access_subset` → `config/risk_silo_cross_access.json`

Each step **appends** a silo folder name when the viewer’s active department is in that config’s merge list **and is not** the silo owner (no duplicate append). **CEO / CFO / CTO** paths that are already `ALL` or fixed lists **do not** use this merge chain.

**Search** still applies **`document_visible_to_viewer`** per file (whitelist, explicit deny, substring rules, Risk/HR/Ops extras, universal-read basenames, auditee audit-report lists, etc.).

| If the Head’s active department is… | Extra silo merged in (when not already that silo) | Mechanism (high level) |
|-------------------------------------|---------------------------------------------------|-------------------------|
| Not **Credit & Loans** | **Credit & Loans** | Credit policy/strategy allowlists; Operations gets extra basenames per `credit_head_cross_access.json`. |
| Not **HR & Admin** | **HR & Admin** | Whitelist + explicit deny (`hr_head_cross_access.json`). |
| Not **IT & Digital** | **IT & Digital** | Whitelist + Risk-only extras + substring deny on basenames (`it_head_cross_access.json`). |
| Not **Operations** | **Operations** | Whitelist + HR substring / Risk expansion + denies (`ops_head_cross_access.json`). |
| Not **Risk & Compliance** | **Risk & Compliance** | Whitelist + IT/Ops AML extras + optional auditee reports per department (`risk_silo_cross_access.json`). |

### Related config files

| File | Purpose |
|------|---------|
| `config/org_structure.json` | Departments & base role access. |
| `config/universal_read_basenames.json` | Basenames readable across allowed silos (extra visibility rules). |
| `config/credit_head_cross_access.json` | Merge Credit + policy/strategy file lists. |
| `config/hr_head_cross_access.json` | Merge HR + cross-read rules. |
| `config/it_head_cross_access.json` | Merge IT + Risk-only extras + deny patterns. |
| `config/ops_head_cross_access.json` | Merge Operations + HR/Risk extensions. |
| `config/risk_silo_cross_access.json` | Merge Risk + AML/auditee rules. |
| `config/operational_staff_vault_denylist.json` | Blocks specific basenames for Operational Staff by silo. |

### Index & regression

- After bulk changes under `knowledge/`, use **🛠️ System Config → Rebuild vault index & search cache** (`_SEARCH_CACHE.json`, `_MASTER_INDEX.md`).
- Example script for merge scope: `scripts/test_merge_cross_silo.py`.

---

## 🛠️ Quick start & operations

**In this section:** (1) two-folder layout & subset rules → (2) first-time steps 1–6 → (3) production checklist → (4) env/CLI notes → (5) tech reference.

---

### 1) Two folders, subsets, and where `.md` comes from

Everything below uses defaults from `core/Utils.py`. Override paths with environment variables or **🛠️ System Config** in the app.

| Layer | Path (default) | Config key | What it is |
| :--- | :--- | :--- | :--- |
| **Raw** | `raw_data/` | `RAW_DATA_PATH` | Drop unstructured files here first. |
| **Cleaned** | `knowledge/` | `CLEANED_DATA_PATH` | The **only** tree GURU indexes—your “cleaned data” vault (name can stay `knowledge/`). |

**Automated pipeline (raw → cleaned)**  
With Streamlit running, the **background monitor** watches `raw_data/`. **`DataRefinery`** calls your **LLM** to classify content, suggest a filename, and write **Markdown + YAML front matter** straight into **`knowledge/<Department>/`**. No second staging folder. **Obsidian does not run this step** and never receives raw drops.

**Subset (who sees what)**  
“Subset” is enforced at **query time** in Python: allowed **department folders** under `knowledge/`, using `config/org_structure.json` and the role you pick in the UI (`SearchWorker` / `RAGOrchestrator`). **Department Heads** additionally get **merged silos** and **per-file RBAC** as described in **§ Organization model**. **Obsidian does not split subsets.** Optionally open `knowledge/` in Obsidian **after** files exist to edit, link, or tag—folder names must still match silos.

| How `.md` gets into `knowledge/` | Details |
| :--- | :--- |
| **Refinery (automated)** | `raw_data/` → LLM classification → `knowledge/<Department>/` (monitor or batch `DataRefinery().scan_and_refine_all()`). |
| **Manual** | Create/edit `.md` in VS Code, Cursor, Obsidian, etc. |
| **Office / PDF** | Optional **[Pandoc](https://pandoc.org/installing.html)** if you use Pandoc-based flows; place output under the right silo. |
| **Bulk import** | Copy pre-cleaned trees into `knowledge/`; department folder names must match **`org_structure.json`**. |

---

### 2) First-time run (steps 1–6)

Do these in order for the PoC.

**1. Install the codebase**

**Option A — Docker (recommended)**

Prerequisites: [Docker](https://docs.docker.com/get-docker/) + [Docker Compose v2](https://docs.docker.com/compose/).

```bash
git clone https://github.com/tong-mini-mac/SAG.git
cd SAG
cp config/.env.example config/.env
# Edit config/.env — set at least GEMINI_API_KEY (or keys for the provider you select in the UI)

mkdir -p knowledge raw_data logs
docker compose up --build
```

Open **http://localhost:8501**

- **Secrets:** real keys live only in `config/.env` (gitignored). Do not commit `.env`.
- **Vault / uploads:** `knowledge/` and `raw_data/` are **bind-mounted** from your host; data persists when the container stops.
- **Compose:** `docker compose` loads `config/.env`; create the file with `cp config/.env.example config/.env` if it does not exist yet.

**Option B — Local Python (same clone + pip as below)**

Requires **Python 3.9+** (the included `Dockerfile` uses **3.11** for the container image).

```bash
git clone https://github.com/tong-mini-mac/SAG.git
cd SAG
pip install -r requirements.txt
```

Optional: create a virtual environment (`python -m venv .venv` then activate) before `pip install`. Optional: install the [Pandoc](https://pandoc.org/installing.html) binary if you rely on Pandoc-based export features (`pypandoc`).

**2. Start the UI**

```bash
streamlit run app.py
```

On Windows, if you maintain a local launcher script (e.g. `start.bat`), you can use that instead—it should `cd` to this folder and run Streamlit with your venv.

**3. Connect an LLM (BYOK)**

1. When the app opens, complete the minimal **API key** step, **or** open **🛠️ System Config** in the sidebar.
2. Choose **Google**, **OpenAI**, or **Anthropic** and paste **your own** API key. Keys stay in the Streamlit session until you close the tab.
3. Optional: click **Save keys to config/.env on this PC** so keys reload on the next run (`config/.env` is gitignored). See `config/.env.example`.

Refinery/raw ingestion **requires** a working key—search and GURU need it too.

**4. Put knowledge on disk — pick one track**

| Track | When to use | What to do |
| :--- | :--- | :--- |
| **A — Trial / cleaned vault** | You already have (or imported) Markdown silos—e.g. demo data, Google Drive sync, manual copy | (1) Folder names under `knowledge/` must match **department `name`** fields in `config/org_structure.json`. (2) Place `.md` files with YAML front matter (`title`, `doc_id`, `tags`, `summary`, …) under `knowledge/<Department>/`. **Obsidian is not required** if files are already there—you can edit with VS Code/Cursor/Obsidian. |
| **B — Raw → cleaned Markdown (automated)** | You have unstructured drops (txt, pasted exports, …) | (1) Ensure step 3 is done—**DataRefinery** calls your LLM. (2) Drop files into **`raw_data/`** (raw). (3) Keep Streamlit running: the **background monitor** writes **`.md` straight into `knowledge/<Department>/`** (cleaned). *(4) Batch alternative from project root (venv active):* `python -c "from core.Refinery import DataRefinery; DataRefinery().scan_and_refine_all()"`. |

Regardless of track, **GURU only reads the cleaned vault** (`CLEANED_DATA_PATH`, default `knowledge/`).

**5. Refresh indexes after bulk changes**

After copying many files or changing paths, open **🛠️ System Config** → **Rebuild vault index & search cache** so `_SEARCH_CACHE.json` / `_MASTER_INDEX.md` stay accurate.

**6. Query with GURU**

Open **🧠 GURU Assistant**, choose **role** and **department**, confirm the **document preview table** matches your simulated access, then ask your question in the chat box.

### 2.1) Role-scoped preview flow (recommended)

To avoid cross-silo confusion and improve answer precision:

1. Select **Identity Simulation (role)** and, when needed, **Active Department**.
2. Review **Documents available to this identity (for drafting questions)**.
3. Draft your question from those visible titles / topics.
4. Run GURU query and verify sources in **View Authorized Sources**.

This is the intended "subset-first" operating pattern for the demo.

---

### 3) Production checklist

Use when “trial data” becomes real content. This repo stays a PoC—you own security, deployment, and governance.

1. **Secrets** — Store keys in **`config/.env`** (gitignored), a vault, or your cloud secret manager—never in git. Restrict OS permissions on that file. Rotate API keys per policy.
2. **Vault matches the org model** — Keep **`knowledge/<Department>/`** folder names aligned with **`config/org_structure.json`**. Remember: **filesystem permissions** on those folders are the practical access boundary; sidebar “roles” only **simulate** RBAC inside the demo UI.
3. **Ingestion governance** — Define who may write to **`raw_data/`**. Review **`DataRefinery`** output—the LLM can mis-label a department. After bulk imports or path changes, run **Rebuild vault index & search cache** (System Config). Optionally add a human QA step before treating new `.md` as authoritative.
4. **Paths & hosting** — Set **Raw data** / **Knowledge vault** paths in **System Config** when the vault lives on another drive or share. Run Streamlit **locally**, **behind VPN**, or in a **container / VM** as appropriate; put a **reverse proxy + TLS** in front if exposing beyond localhost.
5. **Monitoring** — Set **`LINE_NOTIFY_TOKEN`** and/or **`DISCORD_WEBHOOK_URL`** in `.env` if you rely on ops alerts from watchdog/monitor paths; verify notifications in lower environments first.
6. **Backups** — Schedule backups of **`knowledge/`**, **`config/`**, and **`logs/`** (and audit artifacts) independently of `git clone`.
7. **Models & spend** — Pin **`GEMINI_MODEL`** / provider equivalents in `.env`; track provider billing and quotas.
8. **Editorial workflow** — For teams maintaining Markdown at scale, standardize on **Obsidian**, **Git**, or internal CMS export into `knowledge/`—pick one workflow and document it for authors.

Complete **steps 1–6** first; then apply this checklist as needed.

---

### Obsidian (optional reminder)

- **Trial with pre-cleaned Markdown:** Obsidian **not required**—the app only reads files on disk.
- **Ongoing editing:** Many teams open `knowledge/` as an [Obsidian](https://obsidian.md/) vault for links/tags/graph; others use VS Code/Cursor. `.obsidian/` remains gitignored.

### 4) Configuration extras (CLI / persistence)

You do **not** need `config/.env` to open the UI—see **§2 step 3** above for BYOK.

- Copy `config/.env.example` → `config/.env` and fill variables, **or** use **Save keys to config/.env on this PC** in the app (`config/.env` is gitignored).
- For **CLI / scripts** without Streamlit, set `SAG_PRIMARY_PROVIDER` to `google`, `openai`, or `anthropic` (same values the in-app save button writes) so the correct API key is read.
- Optional notifications:
  - `LINE_NOTIFY_TOKEN=...`
  - `DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...`

### 5) Tech reference

| Category | Technology | Purpose |
| :--- | :--- | :--- |
| **Packaging** | `Docker` + Compose | Optional reproducible runtime; bind-mount `knowledge/` and `raw_data/` from the host |
| **Orchestration** | `Python 3.9+` (3.11 in Docker image) | Core control logic |
| **Logic Layer** | `Gemini 2.5 Flash` (+ OpenAI / Anthropic optional in UI) | Query interpretation & response synthesis |
| **Storage** | Markdown vault (`knowledge/`, Obsidian-compatible) | Distributed silos on disk |
| **UI Framework** | `Streamlit` | Enterprise Guru dashboard |
| **Resilience** | `Industrial Watchdog` | PID lock, auto-recovery, optional LINE/Discord alerts |

---

**Built with respect for the craft.**
*Architected by SAG Builder (Bangkok, Thailand).*

*PS: https://www.linkedin.com/in/vittaya-lertbuiasin-13b258149/*
