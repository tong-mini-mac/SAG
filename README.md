<div align="center">
  <img src="docs/img/architecture.png" width="100%" alt="RAG-Destroyer: Obsidian Graph x Subset Architecture">
  <h1>🏛️ RAG-Destroyer: The Zero-Vector-DB Architecture</h1>
  <p><b>Deterministic Knowledge Retrieval for the LLM OS Era</b></p>
</div>

<br>

> *"An LLM is the CPU of an emerging operating system."* — **Andrej Karpathy**

### 💡 Inspiration: Standing on the Shoulders of Giants
This project exists because of **Andrej Karpathy's** brilliant vision of the "LLM OS". He proposed that an LLM shouldn't just be a chatbot, but the core processor of a new operating system—capable of reading files, managing memory, and respecting user permissions natively. 

While the AI industry rushed to dump enterprise data into complex, multi-million dollar, black-box Vector Databases, they forgot the fundamental requirement of any Operating System: **A deterministic, permission-aware File System.**

**RAG-Destroyer** (Lom RAG) is my humble attempt to build that missing layer.

---

## 🧪 Proving the Theory: A Manifesto for GURU in the Box
**This project was built to prove a theory, not to be sold as a commercial product.**

The goal of **RAG-Destroyer** is to serve as a **Proof of Concept (PoC)** to demonstrate a singular truth: *A deterministic, Zero-Vector-DB architecture using the "Subset Theory" can eliminate Data Leakage and Hallucination in high-security environments.*

I am not looking for profit or a commercial software license. My only objective was to prove that this architectural approach—the "Lom RAG" philosophy—is the correct foundation for enterprise-grade AI security.

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
- **Industrial Resilience**: Integrated Safety-Cut (Circuit Breaker) and Industrial Operational Watchdog.
- **Demo Audit Layer**: AI-on-AI QC Judging and Performance Dashboard (Built for continuous improvement).

---

## 🛡️ Data Privacy & GitHub Policy
> [!WARNING]
> This repository contains **Zero Private Data**.
> 1. **Code Only**: Only the core orchestration, logic, and UI code is maintained on GitHub.
> 2. **No Vault Access**: The `.obsidian/` folder and `knowledge/` (Markdown Silos) are strictly ignored via `.gitignore`.
> 3. **Google Drive Isolation**: Local CloudStorage paths are never uploaded.
> 4. **Audit Logs**: Demo audit logs used for code refinement are kept local to the developer environment.

---

## 🛠️ Tech Stack & Quick Start

### Installation
```bash
git clone https://github.com/vittaya1973/RAG-Destroyer.git
cd RAG-Destroyer
pip install -r requirements.txt
```

### Configuration
Update `config/.env` with your API keys:
```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
LINE_NOTIFY_TOKEN=Optional_Token
```

### Run the UI
```bash
streamlit run app.py
```

| Category | Technology | Purpose |
| :--- | :--- | :--- |
| **Orchestration** | `Python 3.9+` | Core control logic |
| **Logic Layer** | `Gemini 2.5 Flash` | Query interpretation & response synthesis |
| **Storage** | `Obsidian (Markdown)` | Distributed knowledge vault |
| **UI Framework** | `Streamlit` | Enterprise Guru dashboard |
| **Resilience** | `Industrial Watchdog` | PID Lock, Auto-Recovery, & LINE Notify |

---

**Built with respect for the craft.**
*Architected by RAG Slayer in Bangkok, Thailand.* 🇹🇭
